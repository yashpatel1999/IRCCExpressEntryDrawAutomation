from datetime import datetime
from typing import Any, Dict, Optional


class DrawRecord:
    def __init__(
        self,
        draw_key,
        draw_number,
        draw_date,
        program,
        invitations,
        crs_cutoff,
        tie_breaking,
        source_url,
        fetched_at,
        content_hash,
    ):
        self.draw_key = draw_key
        self.draw_number = draw_number
        self.draw_date = draw_date
        self.program = program
        self.invitations = invitations
        self.crs_cutoff = crs_cutoff
        self.tie_breaking = tie_breaking
        self.source_url = source_url
        self.fetched_at = fetched_at
        self.content_hash = content_hash

    def to_dict(self):
        return {
            "draw_key": self.draw_key,
            "draw_number": self.draw_number,
            "draw_date": self.draw_date,
            "program": self.program,
            "invitations": self.invitations,
            "crs_cutoff": self.crs_cutoff,
            "tie_breaking": self.tie_breaking,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at,
            "content_hash": self.content_hash,
        }


def utc_now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
