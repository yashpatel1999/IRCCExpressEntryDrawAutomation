import requests


DEFAULT_SOURCE_URL = (
    "https://www.canada.ca/en/immigration-refugees-citizenship/corporate/"
    "mandate/policies-operational-instructions-agreements/ministerial-instructions/"
    "express-entry-rounds.html"
)

DEFAULT_TIMEOUT_SECONDS = 10


class FetchResult:
    def __init__(self, url, status_code, html):
        self.url = url
        self.status_code = status_code
        self.html = html


def normalize_html(html):
    return "\n".join(line.rstrip() for line in html.splitlines()).strip()


def fetch_ircc_rounds_page(url=DEFAULT_SOURCE_URL, timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
    response = requests.get(
        url,
        timeout=timeout_seconds,
        headers={"User-Agent": "IRCCExpressEntryDrawAutomation/0.1"},
    )
    response.raise_for_status()
    return FetchResult(url=url, status_code=response.status_code, html=normalize_html(response.text))
