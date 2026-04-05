from ircc_draw_automation.browser_source import fetch_browser_source
from ircc_draw_automation.fetcher import DEFAULT_SOURCE_URL, fetch_http_source
from ircc_draw_automation.models import SchedulerRunResult, utc_now_iso
from ircc_draw_automation.parser import parse_latest_draw_from_html, parse_latest_draw_from_rows
from ircc_draw_automation.state_store import JsonStateStore


def run_check(
    source_url=DEFAULT_SOURCE_URL,
    state_file=None,
    dry_run=False,
    use_browser=False,
    browser_rows_file=None,
    http_provider=None,
    browser_provider=None,
):
    http_provider = http_provider or fetch_http_source
    browser_provider = browser_provider or fetch_browser_source
    state_store = JsonStateStore(state_file)
    current_state = state_store.read_state()
    diagnostics = {"state_file": state_store.path}

    if use_browser:
        source_payload = browser_provider(url=source_url, fixture_path=browser_rows_file)
        latest_draw = parse_latest_draw_from_rows(source_payload.rows, source_payload.source_url)
        reason = "browser_forced"
        used_fallback = False
    else:
        try:
            source_payload = http_provider(url=source_url)
            latest_draw = parse_latest_draw_from_html(source_payload.html, source_payload.source_url)
            reason = "http_primary_success"
            used_fallback = False
        except Exception as http_error:
            diagnostics["http_error"] = str(http_error)
            source_payload = browser_provider(url=source_url, fixture_path=browser_rows_file)
            latest_draw = parse_latest_draw_from_rows(source_payload.rows, source_payload.source_url)
            reason = "http_failed_browser_used"
            used_fallback = True

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
            }
        )
        state_updated = True

    return SchedulerRunResult(
        latest_draw=latest_draw,
        changed=changed,
        reason=reason,
        change_status=change_status,
        source_kind=source_payload.source_kind,
        used_fallback=used_fallback,
        state_updated=state_updated,
        diagnostics=diagnostics,
    )
