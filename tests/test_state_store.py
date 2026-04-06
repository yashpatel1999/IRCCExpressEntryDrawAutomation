import json
import os
import tempfile
import unittest

from ircc_draw_automation.state_store import JsonStateStore


class StateStoreTests(unittest.TestCase):
    def test_read_state_returns_defaults_when_missing(self):
        with tempfile.TemporaryDirectory() as tempdir:
            store = JsonStateStore(os.path.join(tempdir, "state.json"))
            state = store.read_state()

            self.assertIsNone(state["last_seen_draw_key"])
            self.assertIn("pool_distribution", state)
            self.assertEqual(state["notifications"], [])

    def test_read_state_returns_defaults_when_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "state.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("")

            store = JsonStateStore(path)
            state = store.read_state()

            self.assertIsNone(state["last_seen_draw_key"])
            self.assertEqual(state["notifications"], [])

    def test_append_notification_persists_history(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = os.path.join(tempdir, "state.json")
            store = JsonStateStore(path)
            store.write_state({"last_seen_draw_key": "2026-04-02_408", "notifications": []})
            store.append_notification(
                {
                    "draw_key": "2026-04-02_408",
                    "sent_at": "2026-04-05T00:00:00Z",
                    "provider": "dry_run",
                    "message_id": None,
                    "reason": "dry_run",
                }
            )

            with open(path, "r") as handle:
                payload = json.load(handle)

            self.assertEqual(len(payload["notifications"]), 1)
            self.assertEqual(payload["notifications"][0]["draw_key"], "2026-04-02_408")
