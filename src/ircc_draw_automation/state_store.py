import json
import os


DEFAULT_STATE_FILE = ".ircc_draw_state.json"


class JsonStateStore:
    def __init__(self, path=None):
        self.path = path or os.environ.get("IRCC_STATE_FILE") or DEFAULT_STATE_FILE

    def read_state(self):
        if not os.path.exists(self.path):
            return {}

        with open(self.path, "r") as handle:
            return json.load(handle)

    def write_state(self, state):
        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        with open(self.path, "w") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
