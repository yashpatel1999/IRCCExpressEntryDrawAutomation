import os
from datetime import datetime

from ircc_draw_automation.enricher import build_message, build_pool_distribution_message
from ircc_draw_automation.config import load_dotenv_file
from ircc_draw_automation.fetcher import DEFAULT_POOL_DISTRIBUTION_URL, DEFAULT_SOURCE_URL, fetch_http_source
from ircc_draw_automation.models import SchedulerRunResult, SourcePayload, utc_now_iso
from ircc_draw_automation.mcp_browser_source import fetch_browser_source
from ircc_draw_automation.notifier import NotificationResult, build_default_notifier
from ircc_draw_automation.observability import get_logger, log_event
from ircc_draw_automation.parser import parse_latest_draw_from_html, parse_latest_draw_from_rows, parse_pool_distribution_from_html
from ircc_draw_automation.state_store import JsonStateStore
from ircc_draw_automation.validator import validate_draw_record


def run_check(
    source_url=DEFAULT_SOURCE_URL,
    pool_distribution_url=DEFAULT_POOL_DISTRIBUTION_URL,
    state_file=None,
    dry_run=False,
    use_browser=False,
    browser_rows_file=None,
    http_provider=None,
    browser_provider=None,
    pool_distribution_provider=None,
    notifier=None,
    logger=None,
):
    load_dotenv_file()
    started_at = utc_now_iso()
    http_provider = http_provider or fetch_http_source
    browser_provider = browser_provider or fetch_browser_source
    pool_distribution_provider = pool_distribution_provider or fetch_http_source
    if notifier is None:
        notifier = build_default_notifier(dry_run=dry_run)
    logger = logger or get_logger()
    state_store = JsonStateStore(state_file)
    current_state = state_store.read_state()
    pool_state = current_state.get("pool_distribution", {})
    state_snapshot = {
        "last_seen_draw_key": current_state.get("last_seen_draw_key"),
        "last_notified_draw_key": current_state.get("last_notified_draw_key"),
        "last_checked_at": current_state.get("last_checked_at"),
        "last_source_kind": current_state.get("last_source_kind"),
        "pool_distribution_last_seen_key": pool_state.get("last_seen_key"),
        "pool_distribution_last_notified_key": pool_state.get("last_notified_key"),
        "notification_count": len(current_state.get("notifications", [])),
    }
    diagnostics = {"state_file": state_store.path}
    log_event(
        logger,
        "run_started",
        source_url=source_url,
        state_file=state_store.path,
        dry_run=dry_run,
        use_browser=use_browser,
        state_snapshot=state_snapshot,
    )

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
    log_event(
        logger,
        "draw_comparison_complete",
        draw_key=latest_draw.draw_key,
        change_status=change_status,
        changed=changed,
        source_kind=source_payload.source_kind,
    )

    if not dry_run:
        state_store.write_state(
            {
                "last_seen_draw_key": latest_draw.draw_key,
                "last_notified_draw_key": current_state.get("last_notified_draw_key"),
                "content_hash": latest_draw.content_hash,
                "last_checked_at": utc_now_iso(),
                "last_source_kind": source_payload.source_kind,
                "pool_distribution": pool_state,
                "notifications": current_state.get("notifications", []),
            }
        )
        state_updated = True
        log_event(logger, "state_updated", draw_key=latest_draw.draw_key, source_kind=source_payload.source_kind)

    notification_result = None
    should_notify = validation.is_valid and latest_draw.draw_key != current_state.get("last_notified_draw_key")
    if should_notify and not dry_run:
        message = build_message(latest_draw)
        try:
            notification_result = notifier.send(message)
        except Exception as exc:
            notification_result = NotificationResult(
                False,
                getattr(notifier, "__class__", type("Notifier", (), {})).__name__.lower(),
                message,
                reason="exception:%s" % exc,
            )
        diagnostics["notification"] = notification_result.to_dict()
        log_event(logger, "notification_sent" if notification_result.sent else "notification_failed", notification=notification_result.to_dict())
        if notification_result.sent:
            state_store.append_notification(
                {
                    "draw_key": latest_draw.draw_key,
                    "sent_at": utc_now_iso(),
                    "provider": notification_result.provider,
                    "message_id": notification_result.message_id,
                    "reason": notification_result.reason,
                }
            )
            state_store.write_state(
                {
                    "last_seen_draw_key": latest_draw.draw_key,
                    "last_notified_draw_key": latest_draw.draw_key,
                    "content_hash": latest_draw.content_hash,
                    "last_checked_at": utc_now_iso(),
                    "last_source_kind": source_payload.source_kind,
                    "pool_distribution": state_store.read_state().get("pool_distribution", pool_state),
                    "notifications": state_store.read_state().get("notifications", []),
                }
            )
    elif not changed and latest_draw.draw_key == current_state.get("last_notified_draw_key"):
        log_event(logger, "notification_skipped", reason="draw_unchanged", draw_key=latest_draw.draw_key)
    elif dry_run:
        log_event(logger, "notification_skipped", reason="dry_run", draw_key=latest_draw.draw_key)
    else:
        log_event(
            logger,
            "notification_skipped",
            reason="validation_failed" if not validation.is_valid else "already_notified",
            draw_key=latest_draw.draw_key,
        )

    log_event(
        logger,
        "run_completed",
        draw_key=latest_draw.draw_key,
        changed=changed,
        state_updated=state_updated,
        notification_sent=bool(notification_result and notification_result.sent),
        source_kind=source_payload.source_kind,
        change_status=change_status,
        state_snapshot=state_snapshot,
    )

    pool_distribution_result = _run_pool_distribution_check(
        pool_distribution_url=pool_distribution_url,
        pool_distribution_provider=pool_distribution_provider,
        state_store=state_store,
        notifier=notifier,
        logger=logger,
        dry_run=dry_run,
        current_state=state_store.read_state(),
    )

    completed_at = utc_now_iso()
    heartbeat = _build_heartbeat(
        previous_checked_at=current_state.get("last_checked_at"),
        started_at=started_at,
    )
    summary = {
        "started_at": started_at,
        "completed_at": completed_at,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "commit_sha": os.environ.get("GITHUB_SHA"),
        "reason": reason,
        "change_status": change_status,
        "changed": changed,
        "source_kind": source_payload.source_kind,
        "used_fallback": used_fallback,
        "state_updated": state_updated,
        "draw_key": latest_draw.draw_key,
        "draw_number": latest_draw.draw_number,
        "draw_date": latest_draw.draw_date,
        "program": latest_draw.program,
        "notification_sent": bool(notification_result and notification_result.sent),
        "notification_provider": notification_result.provider if notification_result else None,
        "notification_reason": notification_result.reason if notification_result else None,
        "state_snapshot_before": state_snapshot,
        "validation": diagnostics.get("validation"),
        "source_diagnostics": diagnostics.get("source_diagnostics"),
        "heartbeat": heartbeat,
        "pool_distribution": pool_distribution_result,
    }
    state_store.write_latest_run_summary(summary)
    state_store.append_run_history(summary)

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


def _run_pool_distribution_check(pool_distribution_url, pool_distribution_provider, state_store, notifier, logger, dry_run, current_state):
    pool_state = current_state.get("pool_distribution", {})
    result = {
        "source_url": pool_distribution_url,
        "checked": False,
        "changed": False,
        "notification_sent": False,
        "reason": None,
    }
    try:
        source_payload = pool_distribution_provider(url=pool_distribution_url)
        distribution = parse_pool_distribution_from_html(source_payload.html, source_payload.source_url)
        result.update(
            {
                "checked": True,
                "distribution_key": distribution.distribution_key,
                "distribution_date": distribution.distribution_date,
                "total_candidates": distribution.total_candidates,
                "source_kind": source_payload.source_kind,
                "changed": distribution.distribution_key != pool_state.get("last_seen_key"),
            }
        )
        log_event(
            logger,
            "pool_distribution_checked",
            distribution_key=distribution.distribution_key,
            distribution_date=distribution.distribution_date,
            changed=result["changed"],
        )

        if not dry_run:
            updated_state = state_store.read_state()
            updated_state["pool_distribution"] = {
                "last_seen_key": distribution.distribution_key,
                "last_notified_key": pool_state.get("last_notified_key"),
                "content_hash": distribution.content_hash,
                "last_checked_at": utc_now_iso(),
                "distribution_date": distribution.distribution_date,
            }
            state_store.write_state(updated_state)

        should_notify = distribution.distribution_key != pool_state.get("last_notified_key")
        if should_notify and not dry_run:
            message = build_pool_distribution_message(distribution)
            try:
                notification_result = notifier.send(message)
            except Exception as exc:
                notification_result = NotificationResult(
                    False,
                    getattr(notifier, "__class__", type("Notifier", (), {})).__name__.lower(),
                    message,
                    reason="exception:%s" % exc,
                )
            result["notification_sent"] = notification_result.sent
            result["notification_provider"] = notification_result.provider
            result["notification_reason"] = notification_result.reason
            log_event(
                logger,
                "pool_distribution_notification_sent" if notification_result.sent else "pool_distribution_notification_failed",
                distribution_key=distribution.distribution_key,
                notification=notification_result.to_dict(),
            )
            if notification_result.sent:
                updated_state = state_store.read_state()
                updated_state["pool_distribution"] = {
                    "last_seen_key": distribution.distribution_key,
                    "last_notified_key": distribution.distribution_key,
                    "content_hash": distribution.content_hash,
                    "last_checked_at": utc_now_iso(),
                    "distribution_date": distribution.distribution_date,
                }
                notifications = updated_state.get("notifications", [])
                notifications.append(
                    {
                        "event_type": "pool_distribution",
                        "draw_key": distribution.distribution_key,
                        "sent_at": utc_now_iso(),
                        "provider": notification_result.provider,
                        "message_id": notification_result.message_id,
                        "reason": notification_result.reason,
                    }
                )
                updated_state["notifications"] = notifications
                state_store.write_state(updated_state)
        else:
            result["reason"] = "dry_run" if dry_run else "already_notified"
            log_event(
                logger,
                "pool_distribution_notification_skipped",
                distribution_key=distribution.distribution_key,
                reason=result["reason"],
            )
    except Exception as exc:
        result["checked"] = False
        result["reason"] = str(exc)
        log_event(logger, "pool_distribution_failed", error=str(exc))

    return result


def _build_heartbeat(previous_checked_at, started_at):
    expected_interval_minutes = 30
    heartbeat = {
        "expected_interval_minutes": expected_interval_minutes,
        "previous_checked_at": previous_checked_at,
        "observed_gap_minutes": None,
        "missed_schedule_suspected": False,
    }
    if not previous_checked_at:
        return heartbeat

    try:
        previous_dt = _parse_utc_iso(previous_checked_at)
        started_dt = _parse_utc_iso(started_at)
    except ValueError:
        heartbeat["parse_error"] = True
        return heartbeat

    observed_gap_minutes = round((started_dt - previous_dt).total_seconds() / 60.0, 2)
    heartbeat["observed_gap_minutes"] = observed_gap_minutes
    heartbeat["missed_schedule_suspected"] = observed_gap_minutes > (expected_interval_minutes * 1.5)
    return heartbeat


def _parse_utc_iso(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
