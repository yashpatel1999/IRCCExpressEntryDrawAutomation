import json
import os
import re

from ircc_draw_automation.fetcher import DEFAULT_SOURCE_URL
from ircc_draw_automation.models import SourcePayload, utc_now_iso


HEADER_KEY_MAP = {
    "round": "draw_number",
    "draw": "draw_number",
    "date": "draw_date",
    "program": "program",
    "invitations issued": "invitations",
    "invitations": "invitations",
    "crs score of lowest ranked candidate invited": "crs_cutoff",
    "crs score": "crs_cutoff",
    "crs": "crs_cutoff",
}


class BrowserSourceUnavailable(RuntimeError):
    pass


def fetch_browser_source(url=DEFAULT_SOURCE_URL, fixture_path=None):
    resolved_path = fixture_path or os.environ.get("IRCC_BROWSER_ROWS_FILE")
    if not resolved_path:
        raise BrowserSourceUnavailable(
            "Browser source is unavailable. Set IRCC_BROWSER_ROWS_FILE or use --browser-rows-file."
        )

    with open(resolved_path, "r") as handle:
        payload = json.load(handle)

    headers = payload.get("headers", [])
    rows = payload.get("rows", [])
    normalized_rows = _normalize_rows(headers, rows)
    if not normalized_rows:
        raise ValueError("Browser source fixture did not contain any recognizable rows.")

    return SourcePayload(
        source_kind="browser",
        source_url=payload.get("source_url", url),
        fetched_at=payload.get("fetched_at", utc_now_iso()),
        html=None,
        rows=normalized_rows,
        diagnostics={"fixture_path": resolved_path, "row_count": len(normalized_rows)},
    )


def _normalize_rows(headers, rows):
    if not rows:
        return []

    if isinstance(rows[0], dict):
        normalized = []
        for row in rows:
            normalized_row = {}
            for key, value in row.items():
                canonical_key = HEADER_KEY_MAP.get(_normalize_header(key))
                if canonical_key:
                    normalized_row[canonical_key] = value
            if normalized_row:
                normalized.append(normalized_row)
        return normalized

    normalized_headers = [HEADER_KEY_MAP.get(_normalize_header(header)) for header in headers]
    normalized_rows = []
    for row in rows:
        normalized_row = {}
        for index, value in enumerate(row):
            if index >= len(normalized_headers):
                continue
            canonical_key = normalized_headers[index]
            if canonical_key:
                normalized_row[canonical_key] = value
        if normalized_row:
            normalized_rows.append(normalized_row)
    return normalized_rows


def _normalize_header(value):
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
