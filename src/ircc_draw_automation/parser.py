import hashlib
import re

from bs4 import BeautifulSoup

from ircc_draw_automation.models import DrawRecord, utc_now_iso


DRAW_NUMBER_PATTERN = re.compile(r"round\s*#?\s*(\d+)|draw\s*#?\s*(\d+)", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"([A-Z][a-z]+ \d{1,2}, \d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"(\d[\d,]*)")
HEADER_KEY_MAP = {
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


def parse_latest_draw(html, source_url):
    return parse_latest_draw_from_html(html, source_url)


def parse_latest_draw_from_html(html, source_url):
    soup = BeautifulSoup(html, "html.parser")
    table_rows = _extract_rows_from_tables(soup)
    if table_rows:
        return parse_latest_draw_from_rows(table_rows, source_url)

    candidate = _find_latest_draw_container(soup)
    if candidate is None:
        raise ValueError("Could not locate a draw container in the IRCC page.")

    parsed_values = _parse_free_text_block(candidate.get_text(" ", strip=True))
    _validate_candidate(parsed_values)
    return _build_draw_record(parsed_values, source_url, parsed_values["hash_basis"])


def parse_latest_draw_from_rows(rows, source_url):
    candidates = []
    for row in rows:
        candidate = _parse_row_candidate(row)
        if candidate is not None:
            candidates.append(candidate)

    if not candidates:
        raise ValueError("Could not parse any draw rows.")

    complete_candidates = [candidate for candidate in candidates if _is_complete_candidate(candidate)]
    if not complete_candidates:
        raise ValueError("Could not parse a complete draw row.")

    latest_candidate = _select_latest_candidate(complete_candidates)
    return _build_draw_record(latest_candidate, source_url, latest_candidate["hash_basis"])


def _extract_rows_from_tables(soup):
    extracted_rows = []
    for table in soup.select("table"):
        headers = _extract_table_headers(table)
        body_rows = table.select("tbody tr")
        if not body_rows:
            body_rows = table.select("tr")

        for row in body_rows:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
            if not cells:
                continue
            normalized_row = _normalize_table_row(headers, cells)
            if normalized_row:
                extracted_rows.append(normalized_row)
    return extracted_rows


def _extract_table_headers(table):
    headers = [header.get_text(" ", strip=True) for header in table.select("thead th")]
    if headers:
        return headers

    first_header_row = table.select_one("tr")
    if not first_header_row:
        return []

    th_cells = first_header_row.find_all("th")
    if not th_cells:
        return []
    return [cell.get_text(" ", strip=True) for cell in th_cells]


def _normalize_table_row(headers, cells):
    normalized = {}
    if headers:
        for index, value in enumerate(cells):
            if index >= len(headers):
                continue
            canonical_key = HEADER_KEY_MAP.get(_normalize_header(headers[index]))
            if canonical_key:
                normalized[canonical_key] = value

    if "draw_number" not in normalized and cells:
        normalized["draw_number"] = cells[0]
    if "draw_date" not in normalized and len(cells) > 1:
        normalized["draw_date"] = cells[1]
    if "program" not in normalized and len(cells) > 2:
        normalized["program"] = cells[2]
    if "invitations" not in normalized and len(cells) > 3:
        normalized["invitations"] = cells[3]
    if "crs_cutoff" not in normalized and len(cells) > 4:
        normalized["crs_cutoff"] = cells[4]

    return normalized


def _parse_row_candidate(row):
    draw_number = _parse_int(row.get("draw_number"))
    draw_date = _extract_draw_date(row.get("draw_date", ""))
    invitations = _parse_int(row.get("invitations"))
    crs_cutoff = _parse_int(row.get("crs_cutoff"))
    program = _clean_text(row.get("program"))

    if draw_number is None and draw_date is None:
        return None

    return {
        "draw_number": draw_number,
        "draw_date": draw_date,
        "program": program,
        "invitations": invitations,
        "crs_cutoff": crs_cutoff,
        "tie_breaking": None,
        "hash_basis": "|".join(
            [
                row.get("draw_number", "") or "",
                row.get("draw_date", "") or "",
                row.get("program", "") or "",
                row.get("invitations", "") or "",
                row.get("crs_cutoff", "") or "",
            ]
        ),
    }


def _select_latest_candidate(candidates):
    return max(candidates, key=_candidate_sort_key)


def _candidate_sort_key(candidate):
    draw_number = candidate.get("draw_number")
    draw_date = candidate.get("draw_date") or ""
    return (draw_number if draw_number is not None else -1, draw_date)


def _is_complete_candidate(candidate):
    required_keys = ("draw_number", "draw_date", "invitations", "crs_cutoff")
    for key in required_keys:
        if candidate.get(key) is None:
            return False
    return True


def _validate_candidate(candidate):
    if not _is_complete_candidate(candidate):
        raise ValueError("Parsed draw is missing one or more required fields.")


def _build_draw_record(parsed_values, source_url, hash_basis):
    content_hash = "sha256:" + hashlib.sha256(hash_basis.encode("utf-8")).hexdigest()
    return DrawRecord(
        draw_key="%s_%s" % (parsed_values["draw_date"], parsed_values["draw_number"]),
        draw_number=parsed_values["draw_number"],
        draw_date=parsed_values["draw_date"],
        program=parsed_values.get("program"),
        invitations=parsed_values["invitations"],
        crs_cutoff=parsed_values["crs_cutoff"],
        tie_breaking=parsed_values.get("tie_breaking"),
        source_url=source_url,
        fetched_at=utc_now_iso(),
        content_hash=content_hash,
    )


def _find_latest_draw_container(soup):
    selectors = ["section.panel", "article", "main", "body"]
    for selector in selectors:
        matches = [tag for tag in soup.select(selector) if _looks_like_draw_block(tag)]
        if matches:
            return matches[0]
    return None


def _looks_like_draw_block(tag):
    text = tag.get_text(" ", strip=True)
    normalized = text.lower()
    required_markers = ("round", "draw", "invitations", "crs")
    return sum(marker in normalized for marker in required_markers) >= 2


def _parse_free_text_block(text):
    return {
        "draw_number": _extract_draw_number(text),
        "draw_date": _extract_draw_date(text),
        "program": _extract_program(text),
        "invitations": _extract_metric(text, ("Invitations issued", "Invitations")),
        "crs_cutoff": _extract_metric(text, ("CRS score of lowest-ranked candidate invited", "CRS")),
        "tie_breaking": None,
        "hash_basis": text,
    }


def _extract_draw_number(text):
    match = DRAW_NUMBER_PATTERN.search(text)
    if match:
        value = next(group for group in match.groups() if group)
        return int(value)
    return _parse_int(text)


def _extract_draw_date(text):
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    raw = match.group(1)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    month_name, day, year = raw.replace(",", "").split()
    month_lookup = {
        "January": "01",
        "February": "02",
        "March": "03",
        "April": "04",
        "May": "05",
        "June": "06",
        "July": "07",
        "August": "08",
        "September": "09",
        "October": "10",
        "November": "11",
        "December": "12",
    }
    return "%s-%s-%02d" % (year, month_lookup[month_name], int(day))


def _extract_metric(text, labels):
    for label in labels:
        pattern = re.compile(r"%s[^0-9]*(\d[\d,]*)" % re.escape(label), re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def _extract_program(text):
    known_programs = [
        "Canadian Experience Class",
        "Provincial Nominee Program",
        "French language proficiency",
        "Healthcare occupations",
        "STEM occupations",
        "Transport occupations",
        "Trades occupations",
        "Agriculture and agri-food occupations",
        "No program specified",
    ]
    lowered = text.lower()
    for program in known_programs:
        if program.lower() in lowered:
            return program
    return None


def _parse_int(text):
    if not text:
        return None
    match = NUMBER_PATTERN.search(text)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _normalize_header(value):
    stripped = value.strip().lower()
    if stripped == "#":
        return "#"
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()


def _clean_text(value):
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
