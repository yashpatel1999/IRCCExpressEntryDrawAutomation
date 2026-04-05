import json
import os


DEFAULT_STATE_FILE = ".ircc_draw_state.json"


class JsonStateStore:
    def __init__(self, path=None):
        self.path = path or os.environ.get("IRCC_STATE_FILE") or DEFAULT_STATE_FILE

    def read_state(self):
        if not os.path.exists(self.path):
            return {
                "last_seen_draw_key": None,
                "content_hash": None,
                "last_checked_at": None,
                "last_source_kind": None,
                "notifications": [],
            }

        with open(self.path, "r") as handle:
            state = json.load(handle)
            state.setdefault("last_seen_draw_key", None)
            state.setdefault("content_hash", None)
            state.setdefault("last_checked_at", None)
            state.setdefault("last_source_kind", None)
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
