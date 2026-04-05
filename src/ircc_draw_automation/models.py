from datetime import datetime


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


class SourcePayload:
    def __init__(self, source_kind, source_url, fetched_at, html=None, rows=None, diagnostics=None):
        self.source_kind = source_kind
        self.source_url = source_url
        self.fetched_at = fetched_at
        self.html = html
        self.rows = rows
        self.diagnostics = diagnostics or {}


class SchedulerRunResult:
    def __init__(
        self,
        latest_draw,
        changed,
        reason,
        change_status,
        source_kind,
        used_fallback,
        state_updated,
        diagnostics=None,
    ):
        self.latest_draw = latest_draw
        self.changed = changed
        self.reason = reason
        self.change_status = change_status
        self.source_kind = source_kind
        self.used_fallback = used_fallback
        self.state_updated = state_updated
        self.diagnostics = diagnostics or {}

    def to_dict(self):
        return {
            "changed": self.changed,
            "reason": self.reason,
            "change_status": self.change_status,
            "source_kind": self.source_kind,
            "used_fallback": self.used_fallback,
            "state_updated": self.state_updated,
            "latest_draw": self.latest_draw.to_dict(),
            "diagnostics": self.diagnostics,
        }
