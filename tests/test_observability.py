import json
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
