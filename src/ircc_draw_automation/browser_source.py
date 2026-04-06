import json
import os
import re

from ircc_draw_automation.fetcher import DEFAULT_POOL_DISTRIBUTION_URL, DEFAULT_SOURCE_URL
from ircc_draw_automation.mcp_client import capture_draw_rows_via_mcp, capture_table_rows_via_mcp
from ircc_draw_automation.models import SourcePayload, utc_now_iso


DRAW_HEADER_KEY_MAP = {
    "#": "draw_number",
    "round": "draw_number",
    "draw": "draw_number",
    "date": "draw_date",
    "round type": "program",
    "program": "program",
    "invitations issued": "invitations",
    "invitations": "invitations",
    "crs score of lowest ranked candidate invited": "crs_cutoff",
    "crs score": "crs_cutoff",
    "crs": "crs_cutoff",
}

POOL_DISTRIBUTION_HEADER_KEY_MAP = {
    "crs score range": "range_label",
    "number of candidates": "candidate_count",
}


class BrowserSourceUnavailable(RuntimeError):
    pass


def fetch_browser_source(url=DEFAULT_SOURCE_URL, fixture_path=None):
    return _fetch_browser_table_source(
        url=url,
        fixture_path=fixture_path,
        header_key_map=DRAW_HEADER_KEY_MAP,
        default_capture=lambda target_url: capture_draw_rows_via_mcp(target_url),
    )


def fetch_pool_distribution_browser_source(url=DEFAULT_POOL_DISTRIBUTION_URL, fixture_path=None):
    return _fetch_browser_table_source(
        url=url,
        fixture_path=fixture_path,
        header_key_map=POOL_DISTRIBUTION_HEADER_KEY_MAP,
        default_capture=lambda target_url: capture_table_rows_via_mcp(
            target_url,
            header_hints=[
                "crs score range",
                "number of candidates",
            ],
        ),
    )


def _fetch_browser_table_source(url, fixture_path, header_key_map, default_capture):
    resolved_path = fixture_path or os.environ.get("IRCC_BROWSER_ROWS_FILE")
    if resolved_path:
        with open(resolved_path, "r") as handle:
            payload = json.load(handle)

        headers = payload.get("headers", [])
        rows = payload.get("rows", [])
        normalized_rows = _normalize_rows(headers, rows, header_key_map)
        if not normalized_rows:
            raise ValueError("Browser source fixture did not contain any recognizable rows.")

        return SourcePayload(
            source_kind="mcp_browser",
            source_url=payload.get("source_url", url),
            fetched_at=payload.get("fetched_at", utc_now_iso()),
            html=None,
            rows=normalized_rows,
            diagnostics={"fixture_path": resolved_path, "row_count": len(normalized_rows)},
        )

    browser_payload = default_capture(url)
    headers = browser_payload.get("headers", [])
    rows = browser_payload.get("rows", [])
    normalized_rows = _normalize_rows(headers, rows, header_key_map)
    if not normalized_rows:
        raise ValueError("MCP browser capture did not return any recognizable rows.")

    return SourcePayload(
        source_kind="mcp_browser",
        source_url=browser_payload.get("source_url", url),
        fetched_at=browser_payload.get("captured_at", utc_now_iso()),
        html=None,
        rows=normalized_rows,
        diagnostics={
            "live_mcp": True,
            "row_count": len(normalized_rows),
        },
    )


def _normalize_rows(headers, rows, header_key_map):
    if not rows:
        return []

    if isinstance(rows[0], dict):
        normalized = []
        for row in rows:
            normalized_row = {}
            for key, value in row.items():
                canonical_key = header_key_map.get(_normalize_header(key))
                if canonical_key:
                    normalized_row[canonical_key] = value
            if normalized_row:
                normalized.append(normalized_row)
        return normalized

    normalized_headers = [header_key_map.get(_normalize_header(header)) for header in headers]
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
    stripped = value.strip().lower()
    if stripped == "#":
        return "#"
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()
