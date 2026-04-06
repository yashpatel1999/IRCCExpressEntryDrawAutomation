import requests

from ircc_draw_automation.models import SourcePayload, utc_now_iso


DEFAULT_SOURCE_URL = (
    "https://www.canada.ca/en/immigration-refugees-citizenship/corporate/"
    "mandate/policies-operational-instructions-agreements/ministerial-instructions/"
    "express-entry-rounds.html"
)
DEFAULT_POOL_DISTRIBUTION_URL = (
    "https://www.canada.ca/en/immigration-refugees-citizenship/services/"
    "immigrate-canada/express-entry/rounds-invitations.html"
)

DEFAULT_TIMEOUT_SECONDS = 10


def normalize_html(html):
    return "\n".join(line.rstrip() for line in html.splitlines()).strip()


def fetch_http_source(url=DEFAULT_SOURCE_URL, timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers={"User-Agent": "IRCCExpressEntryDrawAutomation/0.1"},
    )
    response.raise_for_status()
    return SourcePayload(
        source_kind="http",
        source_url=url,
        fetched_at=utc_now_iso(),
        html=normalize_html(response.text),
        rows=None,
        diagnostics={"status_code": response.status_code},
    )
