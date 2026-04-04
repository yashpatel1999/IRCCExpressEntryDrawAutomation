from ircc_draw_automation.fetcher import DEFAULT_SOURCE_URL, fetch_ircc_rounds_page
from ircc_draw_automation.parser import parse_latest_draw


class SchedulerRunResult:
    def __init__(self, latest_draw, changed, reason):
        self.latest_draw = latest_draw
        self.changed = changed
        self.reason = reason


def run_check(last_seen_draw_key=None, source_url=DEFAULT_SOURCE_URL):
    fetched = fetch_ircc_rounds_page(url=source_url)
    latest_draw = parse_latest_draw(fetched.html, source_url=fetched.url)
    changed = latest_draw.draw_key != last_seen_draw_key
    reason = "new_draw_detected" if changed else "draw_already_seen"
    return SchedulerRunResult(latest_draw=latest_draw, changed=changed, reason=reason)
