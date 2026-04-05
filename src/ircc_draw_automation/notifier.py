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


class NtfyNotifier(Notifier):
    def __init__(
        self,
        server_url=None,
        topic=None,
        title=None,
        username=None,
        password=None,
        token=None,
    ):
        self.server_url = (server_url or os.environ.get("NTFY_SERVER_URL") or "https://ntfy.sh").rstrip("/")
        self.topic = topic or os.environ.get("NTFY_TOPIC")
        self.title = title or os.environ.get("NTFY_TITLE") or "IRCC Express Entry Draw Alert"
        self.username = username or os.environ.get("NTFY_USERNAME")
        self.password = password or os.environ.get("NTFY_PASSWORD")
        self.token = token or os.environ.get("NTFY_TOKEN")

    def configured(self):
        return bool(self.server_url and self.topic)

    def _build_headers(self):
        headers = {
            "Title": self.title,
            "Priority": "4",
        }
        if self.token:
            headers["Authorization"] = "Bearer %s" % self.token
        return headers

    def send(self, message):
        if not self.configured():
            return NotificationResult(False, "ntfy", message, reason="ntfy_not_configured")

        url = "%s/%s" % (self.server_url, self.topic)
        auth = None
        if self.username and self.password:
            auth = (self.username, self.password)
        response = requests.post(
            url,
            data=message.encode("utf-8"),
            headers=self._build_headers(),
            auth=auth,
            timeout=20,
        )
        if response.status_code >= 400:
            return NotificationResult(
                False,
                "ntfy",
                message,
                reason="ntfy_http_%s" % response.status_code,
            )

        message_id = None
        try:
            payload = response.json()
            message_id = payload.get("id")
        except ValueError:
            payload = None

        return NotificationResult(True, "ntfy", message, message_id=message_id, reason="sent")


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


def build_default_notifier(dry_run=False):
    notifier = NtfyNotifier()
    if not notifier.configured():
        notifier = TwilioNotifier()
    if dry_run or not notifier.configured():
        notifier = DryRunNotifier()
    return notifier
