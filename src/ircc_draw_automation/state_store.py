import json
import os


DEFAULT_STATE_FILE = ".ircc_draw_state.json"


class JsonStateStore:
    def __init__(self, path=None):
        self.path = path or os.environ.get("IRCC_STATE_FILE") or DEFAULT_STATE_FILE

    def read_state(self):
        if not os.path.exists(self.path):
            return _default_state()

        with open(self.path, "r", encoding="utf-8") as handle:
            raw_state = handle.read().strip()

        if not raw_state:
            return _default_state()

        try:
            state = json.loads(raw_state)
        except ValueError:
            return _default_state()

        state.setdefault("last_seen_draw_key", None)
        state.setdefault("last_notified_draw_key", None)
        state.setdefault("content_hash", None)
        state.setdefault("last_checked_at", None)
        state.setdefault("last_source_kind", None)
        state.setdefault(
            "pool_distribution",
            {
                "last_seen_key": None,
                "last_notified_key": None,
                "content_hash": None,
                "last_checked_at": None,
                "distribution_date": None,
            },
        )
        state.setdefault("notifications", [])
        return state

    def write_state(self, state):
        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(self.path, "w") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)

    def append_notification(self, notification):
        state = self.read_state()
        notifications = state.get("notifications", [])
        notifications.append(notification)
        state["notifications"] = notifications
        self.write_state(state)

    def write_latest_run_summary(self, summary):
        path = _summary_path(self.path)
        _write_json(path, summary)

    def append_run_history(self, summary):
        path = _history_path(self.path)
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, sort_keys=True) + "\n")


def _default_state():
    return {
        "last_seen_draw_key": None,
        "last_notified_draw_key": None,
        "content_hash": None,
        "last_checked_at": None,
        "last_source_kind": None,
        "pool_distribution": {
            "last_seen_key": None,
            "last_notified_key": None,
            "content_hash": None,
            "last_checked_at": None,
            "distribution_date": None,
        },
        "notifications": [],
    }


def _summary_path(state_path):
    return os.environ.get("IRCC_LATEST_RUN_SUMMARY_FILE") or os.path.join(_state_directory(state_path), "latest_run_summary.json")


def _history_path(state_path):
    return os.environ.get("IRCC_RUN_HISTORY_FILE") or os.path.join(_state_directory(state_path), "run_history.jsonl")


def _state_directory(state_path):
    directory = os.path.dirname(state_path)
    return directory or "."


def _write_json(path, payload):
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
