import hashlib
import re

from bs4 import BeautifulSoup, Tag

from ircc_draw_automation.models import DrawRecord, utc_now_iso


DRAW_NUMBER_PATTERN = re.compile(r"round\s*#?\s*(\d+)|draw\s*#?\s*(\d+)", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"([A-Z][a-z]+ \d{1,2}, \d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
NUMBER_PATTERN = re.compile(r"(\d[\d,]*)")


def parse_latest_draw(html, source_url):
    soup = BeautifulSoup(html, "html.parser")
    parsed_row = _parse_latest_table_row(soup)
    if parsed_row is not None:
        candidate, parsed_values = parsed_row
    else:
        candidate = _find_latest_draw_container(soup)
        if candidate is None:
            raise ValueError("Could not locate a draw container in the IRCC page.")
        parsed_values = _parse_free_text_block(candidate.get_text(" ", strip=True))

    if parsed_values["draw_number"] is None or parsed_values["draw_date"] is None:
        raise ValueError("Could not locate a draw container in the IRCC page.")

    content_hash = "sha256:" + hashlib.sha256(str(candidate).encode("utf-8")).hexdigest()

    return DrawRecord(
        draw_key="%s_%s" % (parsed_values["draw_date"], parsed_values["draw_number"]),
        draw_number=parsed_values["draw_number"],
        draw_date=parsed_values["draw_date"],
        program=parsed_values["program"],
        invitations=parsed_values["invitations"],
        crs_cutoff=parsed_values["crs_cutoff"],
        tie_breaking=None,
        source_url=source_url,
        fetched_at=utc_now_iso(),
        content_hash=content_hash,
    )


def _parse_latest_table_row(soup):
    table_rows = soup.select("table tbody tr") or soup.select(".table tbody tr") or soup.select("main table tr")
    for row in table_rows:
        parsed_values = _parse_table_row(row)
        if parsed_values is not None:
            return row, parsed_values
    return None


def _parse_table_row(row):
    cells = row.find_all(["td", "th"])
    if not cells:
        return None

    cell_texts = [cell.get_text(" ", strip=True) for cell in cells]
    combined_text = " ".join(cell_texts)
    draw_date = _extract_draw_date(combined_text)
    if draw_date is None:
        return None

    draw_number = _extract_draw_number(combined_text)
    if draw_number is None and cell_texts:
        draw_number = _parse_int(cell_texts[0])

    invitations = _extract_metric(combined_text, ("Invitations issued", "Invitations"))
    if invitations is None and len(cell_texts) >= 4:
        invitations = _parse_int(cell_texts[3])

    crs_cutoff = _extract_metric(combined_text, ("CRS score of lowest-ranked candidate invited", "CRS"))
    if crs_cutoff is None and len(cell_texts) >= 5:
        crs_cutoff = _parse_int(cell_texts[4])

    program = _extract_program(combined_text)
    if program is None:
        for cell_text in cell_texts:
            if not _parse_int(cell_text) and _extract_draw_date(cell_text) is None:
                program = cell_text
                break

    return {
        "draw_number": draw_number,
        "draw_date": draw_date,
        "program": program,
        "invitations": invitations,
        "crs_cutoff": crs_cutoff,
    }


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
    }


def _extract_draw_number(text):
    match = DRAW_NUMBER_PATTERN.search(text)
    if not match:
        return None
    value = next(group for group in match.groups() if group)
    return int(value)


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
    return f"{year}-{month_lookup[month_name]}-{int(day):02d}"


def _extract_metric(text, labels):
    for label in labels:
        pattern = re.compile(rf"{re.escape(label)}[^0-9]*(\d[\d,]*)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def _extract_program(text):
    lowered = text.lower()
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
