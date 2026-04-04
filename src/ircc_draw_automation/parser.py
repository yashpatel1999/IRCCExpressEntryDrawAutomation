import hashlib
import re
from typing import Iterable

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
    candidate = _find_latest_draw_container(soup)
    if candidate is None:
        raise ValueError("Could not locate a draw container in the IRCC page.")

    block_text = candidate.get_text(" ", strip=True)
    draw_number = _extract_draw_number(block_text)
    draw_date = _extract_draw_date(block_text)
    invitations = _extract_metric(block_text, ("Invitations issued", "Invitations"))
    crs_cutoff = _extract_metric(block_text, ("CRS score of lowest-ranked candidate invited", "CRS"))
    program = _extract_program(block_text)
    content_hash = "sha256:" + hashlib.sha256(str(candidate).encode("utf-8")).hexdigest()

    key_date = draw_date or "unknown-date"
    key_number = draw_number if draw_number is not None else "unknown-draw"

    return DrawRecord(
        draw_key=f"{key_date}_{key_number}",
        draw_number=draw_number,
        draw_date=draw_date,
        program=program,
        invitations=invitations,
        crs_cutoff=crs_cutoff,
        tie_breaking=None,
        source_url=source_url,
        fetched_at=utc_now_iso(),
        content_hash=content_hash,
    )


def _find_latest_draw_container(soup):
    selectors = [
        "table tbody tr",
        ".table tbody tr",
        "main table tr",
        "section.panel",
        "article",
    ]
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

    all_numbers = NUMBER_PATTERN.findall(text)
    return int(all_numbers[0].replace(",", "")) if all_numbers else None


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
