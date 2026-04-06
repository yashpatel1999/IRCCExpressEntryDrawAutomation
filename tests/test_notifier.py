import unittest
from contextlib import contextmanager
import os
from unittest.mock import Mock, patch

from ircc_draw_automation.notifier import DryRunNotifier, NtfyNotifier, TwilioNotifier, build_default_notifier, describe_notifier_config, get_notification_title


class NotifierTests(unittest.TestCase):
    @contextmanager
    def _temporary_env(self, **values):
        original = dict(os.environ)
        os.environ.clear()
        os.environ.update(values)
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_dry_run_notifier_marks_message_as_sent(self):
        notifier = DryRunNotifier()
        result = notifier.send("hello")

        self.assertTrue(result.sent)
        self.assertEqual(result.provider, "dry_run")
        self.assertEqual(result.reason, "dry_run")

    def test_twilio_notifier_reports_not_configured_without_env(self):
        notifier = TwilioNotifier(account_sid=None, auth_token=None, from_number=None, to_number=None)
        result = notifier.send("hello")

        self.assertFalse(result.sent)
        self.assertEqual(result.reason, "twilio_not_configured")

    def test_ntfy_notifier_reports_not_configured_without_env(self):
        with self._temporary_env():
            notifier = NtfyNotifier(server_url=None, topic=None)
            result = notifier.send("hello")

            self.assertFalse(result.sent)
            self.assertEqual(result.reason, "ntfy_not_configured")

    @patch("ircc_draw_automation.notifier.requests.post")
    def test_ntfy_notifier_sends_message_to_topic(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "abc123"}
        mock_post.return_value = mock_response

        notifier = NtfyNotifier(
            server_url="https://ntfy.sh",
            topic="ircc-draw-test-topic",
            title="IRCC Alert",
        )
        result = notifier.send("New IRCC draw")

        self.assertTrue(result.sent)
        self.assertEqual(result.provider, "ntfy")
        self.assertEqual(result.message_id, "abc123")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://ntfy.sh/ircc-draw-test-topic")
        self.assertEqual(kwargs["data"], b"New IRCC draw")
        self.assertEqual(kwargs["headers"]["Title"], "IRCC Alert")

    def test_default_notifier_uses_dry_run_when_unconfigured(self):
        with self._temporary_env():
            notifier = build_default_notifier(dry_run=False)
            self.assertIsInstance(notifier, DryRunNotifier)

    def test_event_specific_ntfy_titles_fall_back_to_base_title(self):
        with self._temporary_env(NTFY_TITLE="Base Title"):
            self.assertEqual(get_notification_title("draw"), "Base Title")
            self.assertEqual(get_notification_title("pool_distribution"), "Base Title")

    def test_event_specific_ntfy_titles_override_base_title(self):
        with self._temporary_env(
            NTFY_TITLE="Base Title",
            NTFY_DRAW_TITLE="Draw Title",
            NTFY_POOL_TITLE="Pool Title",
        ):
            self.assertEqual(get_notification_title("draw"), "Draw Title")
            self.assertEqual(get_notification_title("pool_distribution"), "Pool Title")

    def test_describe_notifier_config_reports_dry_run_when_ntfy_missing(self):
        with self._temporary_env():
            payload = describe_notifier_config(dry_run=False)
            self.assertEqual(payload["selected_provider"], "dry_run")
            self.assertFalse(payload["ntfy_configured"])
            self.assertFalse(payload["ntfy_topic_present"])

    def test_describe_notifier_config_reports_ntfy_when_configured(self):
        with self._temporary_env(NTFY_SERVER_URL="https://ntfy.sh", NTFY_TOPIC="topic"):
            payload = describe_notifier_config(dry_run=False)
            self.assertEqual(payload["selected_provider"], "ntfy")
            self.assertTrue(payload["ntfy_configured"])
            self.assertTrue(payload["ntfy_topic_present"])
