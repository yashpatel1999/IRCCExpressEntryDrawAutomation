from ircc_draw_automation.enricher import build_message
from ircc_draw_automation.fetcher import DEFAULT_SOURCE_URL, fetch_http_source
from ircc_draw_automation.models import SchedulerRunResult, utc_now_iso
from ircc_draw_automation.mcp_browser_source import fetch_browser_source
from ircc_draw_automation.notifier import DryRunNotifier, NtfyNotifier, TwilioNotifier
from ircc_draw_automation.observability import get_logger, log_event
from ircc_draw_automation.parser import parse_latest_draw_from_html, parse_latest_draw_from_rows
from ircc_draw_automation.state_store import JsonStateStore
from ircc_draw_automation.validator import validate_draw_record


def run_check(
    source_url=DEFAULT_SOURCE_URL,
    state_file=None,
    dry_run=False,
    use_browser=False,
    browser_rows_file=None,
    http_provider=None,
    browser_provider=None,
    notifier=None,
    logger=None,
):
    http_provider = http_provider or fetch_http_source
    browser_provider = browser_provider or fetch_browser_source
    if notifier is None:
        notifier = NtfyNotifier()
        if not notifier.configured():
            notifier = TwilioNotifier()
        if dry_run or not notifier.configured():
            notifier = DryRunNotifier()
    logger = logger or get_logger()
    state_store = JsonStateStore(state_file)
    current_state = state_store.read_state()
    diagnostics = {"state_file": state_store.path}
    log_event(logger, "run_started", source_url=source_url, state_file=state_store.path, dry_run=dry_run, use_browser=use_browser)

    if use_browser:
        source_payload = browser_provider(url=source_url, fixture_path=browser_rows_file)
        latest_draw = parse_latest_draw_from_rows(source_payload.rows, source_payload.source_url)
        validation = validate_draw_record(latest_draw)
        if not validation.is_valid:
            raise ValueError("Forced browser path produced invalid data: %s" % validation.reason)
        reason = "browser_forced"
        used_fallback = False
        diagnostics["validation"] = validation.to_dict()
        log_event(logger, "browser_forced", validation=validation.to_dict(), source_kind=source_payload.source_kind)
    else:
        http_error = None
        fallback_reason = None
        try:
            source_payload = http_provider(url=source_url)
            latest_draw = parse_latest_draw_from_html(source_payload.html, source_payload.source_url)
            validation = validate_draw_record(latest_draw)
            diagnostics["validation"] = validation.to_dict()
            if validation.is_valid:
                reason = "http_primary_success"
                used_fallback = False
                log_event(logger, "http_parse_valid", validation=validation.to_dict())
            else:
                fallback_reason = "http_parse_low_confidence_browser_used"
                http_error = ValueError("HTTP parse did not pass validation: %s" % validation.reason)
                log_event(logger, "http_parse_invalid", validation=validation.to_dict(), reason=fallback_reason)
        except Exception as exc:
            http_error = exc
            fallback_reason = "http_failed_browser_used"
            log_event(logger, "http_failed", error=str(exc), reason=fallback_reason)

        if http_error is not None and (not diagnostics.get("validation") or not diagnostics["validation"].get("is_valid")):
            diagnostics["http_error"] = str(http_error)
            source_payload = browser_provider(url=source_url, fixture_path=browser_rows_file)
            latest_draw = parse_latest_draw_from_rows(source_payload.rows, source_payload.source_url)
            validation = validate_draw_record(latest_draw)
            if not validation.is_valid:
                raise ValueError("Browser fallback produced invalid data: %s" % validation.reason)
            reason = fallback_reason or "http_failed_browser_used"
            used_fallback = True
            diagnostics["validation"] = validation.to_dict()
            log_event(logger, "browser_fallback_used", validation=validation.to_dict(), source_kind=source_payload.source_kind)

    changed = latest_draw.draw_key != current_state.get("last_seen_draw_key")
    change_status = "new_draw_detected" if changed else "draw_already_seen"
    state_updated = False
    diagnostics["source_diagnostics"] = source_payload.diagnostics

    if not dry_run:
        state_store.write_state(
            {
                "last_seen_draw_key": latest_draw.draw_key,
                "content_hash": latest_draw.content_hash,
                "last_checked_at": utc_now_iso(),
                "last_source_kind": source_payload.source_kind,
                "notifications": current_state.get("notifications", []),
            }
        )
        state_updated = True
        log_event(logger, "state_updated", draw_key=latest_draw.draw_key, source_kind=source_payload.source_kind)

    notification_result = None
    should_notify = changed and validation.is_valid
    if should_notify and not dry_run:
        message = build_message(latest_draw)
        notification_result = notifier.send(message)
        diagnostics["notification"] = notification_result.to_dict()
        log_event(logger, "notification_sent" if notification_result.sent else "notification_failed", notification=notification_result.to_dict())
        if notification_result.sent and not dry_run:
            state_store.append_notification(
                {
                    "draw_key": latest_draw.draw_key,
                    "sent_at": utc_now_iso(),
                    "provider": notification_result.provider,
                    "message_id": notification_result.message_id,
                    "reason": notification_result.reason,
                }
            )

    return SchedulerRunResult(
        latest_draw=latest_draw,
        changed=changed,
        reason=reason,
        change_status=change_status,
        source_kind=source_payload.source_kind,
        used_fallback=used_fallback,
        state_updated=state_updated,
        notification_result=notification_result,
        diagnostics=diagnostics,
    )
