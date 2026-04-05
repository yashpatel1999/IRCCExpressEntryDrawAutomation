import os

import requests


class NotificationResult:
    def __init__(self, sent, provider, message, message_id=None, reason=None):
        self.sent = sent
        self.provider = provider
        self.message = message
        self.message_id = message_id
        self.reason = reason

    def to_dict(self):
        return {
            "sent": self.sent,
            "provider": self.provider,
            "message": self.message,
            "message_id": self.message_id,
            "reason": self.reason,
        }


class Notifier(object):
    def send(self, message):
        raise NotImplementedError


class DryRunNotifier(Notifier):
    def send(self, message):
        return NotificationResult(True, "dry_run", message, reason="dry_run")


class TwilioNotifier(Notifier):
    def __init__(self, account_sid=None, auth_token=None, from_number=None, to_number=None):
        self.account_sid = account_sid or os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.environ.get("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.environ.get("TWILIO_FROM_NUMBER")
        self.to_number = to_number or os.environ.get("TWILIO_TO_NUMBER")

    def configured(self):
        return all([self.account_sid, self.auth_token, self.from_number, self.to_number])

    def send(self, message):
        if not self.configured():
            return NotificationResult(False, "twilio", message, reason="twilio_not_configured")

        url = "https://api.twilio.com/2010-04-01/Accounts/{0}/Messages.json".format(self.account_sid)
        response = requests.post(
            url,
            data={
                "From": self.from_number,
                "To": self.to_number,
                "Body": message,
            },
            auth=(self.account_sid, self.auth_token),
            timeout=20,
        )
        if response.status_code >= 400:
            return NotificationResult(
                False,
                "twilio",
                message,
                reason="twilio_http_%s" % response.status_code,
            )

        payload = response.json()
        return NotificationResult(True, "twilio", message, message_id=payload.get("sid"), reason="sent")
