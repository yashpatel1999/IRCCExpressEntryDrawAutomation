import unittest

from ircc_draw_automation.notifier import DryRunNotifier, TwilioNotifier


class NotifierTests(unittest.TestCase):
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
