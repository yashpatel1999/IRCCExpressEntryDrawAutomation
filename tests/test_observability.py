import json
import os
import unittest
from unittest.mock import Mock

from ircc_draw_automation.observability import log_event


class ObservabilityTests(unittest.TestCase):
    def test_log_event_emits_json(self):
        logger = Mock()

        log_event(logger, "run_started", source_url="https://example.com")

        logger.info.assert_called_once()
        payload = json.loads(logger.info.call_args[0][0])
        self.assertEqual(payload["event"], "run_started")
        self.assertEqual(payload["source_url"], "https://example.com")

    def test_log_event_includes_github_runtime_context(self):
        logger = Mock()
        original = dict(os.environ)
        try:
            os.environ["GITHUB_SHA"] = "abc123"
            os.environ["GITHUB_RUN_ID"] = "42"
            os.environ["GITHUB_RUN_ATTEMPT"] = "2"

            log_event(logger, "run_started", source_url="https://example.com")

            payload = json.loads(logger.info.call_args[0][0])
            self.assertEqual(payload["commit_sha"], "abc123")
            self.assertEqual(payload["workflow_run_id"], "42")
            self.assertEqual(payload["workflow_run_attempt"], "2")
        finally:
            os.environ.clear()
            os.environ.update(original)
