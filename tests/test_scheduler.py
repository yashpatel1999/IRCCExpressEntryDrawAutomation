import os
import tempfile
import unittest
import json

from ircc_draw_automation.browser_source import fetch_browser_source
from ircc_draw_automation.models import SourcePayload
from ircc_draw_automation.notifier import NotificationResult
from ircc_draw_automation.scheduler import run_check


HTML_FIXTURE = """
<html>
  <body>
    <main>
      <table>
        <thead>
          <tr>
            <th>Round</th>
            <th>Date</th>
            <th>Program</th>
            <th>Invitations issued</th>
            <th>CRS score of lowest-ranked candidate invited</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>408</td>
            <td>April 2, 2026</td>
            <td>Trades Occupations, 2026-Version 3</td>
            <td>3,000</td>
            <td>477</td>
          </tr>
        </tbody>
      </table>
    </main>
  </body>
</html>
"""


BROKEN_HTML_FIXTURE = """
<html>
  <body>
    <main>
      <table>
        <thead>
          <tr><th>Round</th><th>Date</th></tr>
        </thead>
        <tbody>
          <tr><td>408</td><td>April 2, 2026</td></tr>
        </tbody>
      </table>
    </main>
  </body>
</html>
"""


STALE_HTML_FIXTURE = """
<html>
  <body>
    <main>
      <table>
        <thead>
          <tr>
            <th>Round</th>
            <th>Date</th>
            <th>Program</th>
            <th>Invitations issued</th>
            <th>CRS score of lowest-ranked candidate invited</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>341</td>
            <td>March 21, 2025</td>
            <td>French language proficiency (Version 1)</td>
            <td>7,500</td>
            <td>379</td>
          </tr>
        </tbody>
      </table>
    </main>
  </body>
</html>
"""


POOL_DISTRIBUTION_HTML = """
<html>
  <body>
    <main>
      <details open>
        <summary>CRS score distribution of candidates in the pool as of March 29, 2026</summary>
        <table>
          <thead>
            <tr>
              <th>CRS score range</th>
              <th>Number of candidates</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>601-1200</td><td>351</td></tr>
            <tr><td>501-600</td><td>11,648</td></tr>
            <tr><td>Total</td><td>230,186</td></tr>
          </tbody>
        </table>
      </details>
    </main>
  </body>
</html>
"""


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.tempdir.name, "state.json")
        self.fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "browser_rows_fixture.json")

    def tearDown(self):
        self.tempdir.cleanup()

    def _pool_distribution_provider(self, url):
        return SourcePayload(
            source_kind="http",
            source_url=url,
            fetched_at="2026-04-05T00:00:00Z",
            html=POOL_DISTRIBUTION_HTML,
            rows=None,
            diagnostics={"status_code": 200},
        )

    def _pool_distribution_browser_provider(self, url, fixture_path=None):
        return SourcePayload(
            source_kind="mcp_browser",
            source_url=url,
            fetched_at="2026-04-05T00:00:00Z",
            html=None,
            rows=[
                {"range_label": "601-1200", "candidate_count": "351"},
                {"range_label": "Total", "candidate_count": "230,186"},
            ],
            diagnostics={"live_mcp": True, "row_count": 2},
        )

    def test_http_success_does_not_invoke_browser_provider(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        def browser_provider(url, fixture_path=None):
            raise AssertionError("browser provider should not be called")

        result = run_check(
            state_file=self.state_file,
            dry_run=True,
            http_provider=http_provider,
            browser_provider=browser_provider,
            pool_distribution_provider=self._pool_distribution_provider,
        )

        self.assertEqual(result.reason, "http_primary_success")
        self.assertEqual(result.source_kind, "http")
        self.assertFalse(result.used_fallback)
        self.assertTrue(result.changed)

    def test_http_fetch_failure_triggers_browser_provider(self):
        def http_provider(url):
            raise RuntimeError("network down")

        def browser_provider(url, fixture_path=None):
            return fetch_browser_source(url=url, fixture_path=self.fixture_path)

        result = run_check(
            state_file=self.state_file,
            dry_run=True,
            http_provider=http_provider,
            browser_provider=browser_provider,
            pool_distribution_provider=self._pool_distribution_provider,
        )

        self.assertEqual(result.reason, "http_failed_browser_used")
        self.assertEqual(result.source_kind, "mcp_browser")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.latest_draw.draw_number, 408)

    def test_http_parse_failure_triggers_browser_provider(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=BROKEN_HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        def browser_provider(url, fixture_path=None):
            return fetch_browser_source(url=url, fixture_path=self.fixture_path)

        result = run_check(
            state_file=self.state_file,
            dry_run=True,
            http_provider=http_provider,
            browser_provider=browser_provider,
            pool_distribution_provider=self._pool_distribution_provider,
        )

        self.assertEqual(result.reason, "http_failed_browser_used")
        self.assertEqual(result.latest_draw.draw_key, "2026-04-02_408")

    def test_stale_http_result_triggers_browser_provider(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=STALE_HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        def browser_provider(url, fixture_path=None):
            return fetch_browser_source(url=url, fixture_path=self.fixture_path)

        result = run_check(
            state_file=self.state_file,
            dry_run=True,
            http_provider=http_provider,
            browser_provider=browser_provider,
            pool_distribution_provider=self._pool_distribution_provider,
        )

        self.assertEqual(result.reason, "http_parse_low_confidence_browser_used")
        self.assertEqual(result.source_kind, "mcp_browser")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.latest_draw.draw_number, 408)

    def test_successful_run_writes_state_and_repeat_run_reports_already_seen(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        class DummyNotifier(object):
            def send(self, message):
                return NotificationResult(True, "dry_run", message, reason="dry_run")

        first_result = run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
            notifier=DummyNotifier(),
        )
        second_result = run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
            notifier=DummyNotifier(),
        )

        self.assertTrue(first_result.state_updated)
        self.assertTrue(os.path.exists(self.state_file))
        self.assertFalse(second_result.changed)
        self.assertEqual(second_result.change_status, "draw_already_seen")
        self.assertTrue(os.path.exists(os.path.join(self.tempdir.name, "latest_run_summary.json")))
        self.assertTrue(os.path.exists(os.path.join(self.tempdir.name, "run_history.jsonl")))

    def test_dry_run_does_not_mutate_state(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        result = run_check(
            state_file=self.state_file,
            dry_run=True,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
        )

        self.assertFalse(result.state_updated)
        self.assertFalse(os.path.exists(self.state_file))
        self.assertIsNone(result.notification_result)

    def test_no_notification_on_dry_run(self):
        calls = []

        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        class DummyNotifier(object):
            def send(self, message):
                calls.append(message)
                raise AssertionError("notifier should not be called during dry_run")

        result = run_check(
            state_file=self.state_file,
            dry_run=True,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
            notifier=DummyNotifier(),
        )

        self.assertEqual(calls, [])
        self.assertIsNone(result.notification_result)

    def test_notification_exception_does_not_fail_run_and_can_retry(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        class FailingNotifier(object):
            def send(self, message):
                raise RuntimeError("ntfy down")

        class SuccessNotifier(object):
            def send(self, message):
                return NotificationResult(True, "dry_run", message, reason="dry_run")

        first_result = run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
            notifier=FailingNotifier(),
        )

        self.assertTrue(first_result.state_updated)
        self.assertIsNotNone(first_result.notification_result)
        self.assertFalse(first_result.notification_result.sent)

        with open(self.state_file, "r", encoding="utf-8") as handle:
            first_state = json.load(handle)

        self.assertEqual(first_state["last_seen_draw_key"], "2026-04-02_408")
        self.assertIsNone(first_state["last_notified_draw_key"])

        second_result = run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
            notifier=SuccessNotifier(),
        )

        self.assertFalse(second_result.changed)
        self.assertTrue(second_result.notification_result.sent)

        with open(self.state_file, "r", encoding="utf-8") as handle:
            second_state = json.load(handle)

        self.assertEqual(second_state["last_notified_draw_key"], "2026-04-02_408")

    def test_run_summary_files_are_human_readable_outputs(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        class DummyNotifier(object):
            def send(self, message):
                return NotificationResult(True, "dry_run", message, reason="dry_run")

        result = run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
            notifier=DummyNotifier(),
        )

        summary_path = os.path.join(self.tempdir.name, "latest_run_summary.json")
        history_path = os.path.join(self.tempdir.name, "run_history.jsonl")

        with open(summary_path, "r", encoding="utf-8") as handle:
            summary = json.load(handle)
        with open(history_path, "r", encoding="utf-8") as handle:
            history_lines = handle.readlines()

        self.assertEqual(summary["draw_key"], result.latest_draw.draw_key)
        self.assertEqual(summary["source_kind"], "http")
        self.assertTrue(summary["notification_sent"])
        self.assertEqual(summary["heartbeat"]["expected_interval_minutes"], 30)
        self.assertFalse(summary["heartbeat"]["missed_schedule_suspected"])
        self.assertEqual(len(history_lines), 1)

    def test_run_summary_marks_large_gap_as_possible_missed_schedule(self):
        existing_state = {
            "last_seen_draw_key": "2026-04-02_408",
            "last_notified_draw_key": "2026-04-02_408",
            "content_hash": "hash",
            "last_checked_at": "2026-04-05T00:00:00Z",
            "last_source_kind": "http",
            "notifications": [],
        }
        with open(self.state_file, "w", encoding="utf-8") as handle:
            json.dump(existing_state, handle)

        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        class DummyNotifier(object):
            def send(self, message):
                return NotificationResult(True, "dry_run", message, reason="dry_run")

        run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
            notifier=DummyNotifier(),
        )

        summary_path = os.path.join(self.tempdir.name, "latest_run_summary.json")
        with open(summary_path, "r", encoding="utf-8") as handle:
            summary = json.load(handle)

        self.assertTrue(summary["heartbeat"]["missed_schedule_suspected"])

    def test_pool_distribution_change_is_persisted_and_notified(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        class DummyNotifier(object):
            def __init__(self):
                self.messages = []

            def send(self, message):
                self.messages.append(message)
                return NotificationResult(True, "dry_run", message, reason="dry_run")

        notifier = DummyNotifier()
        run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=self._pool_distribution_provider,
            notifier=notifier,
        )

        with open(self.state_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        self.assertEqual(payload["pool_distribution"]["distribution_date"], "2026-03-29")
        self.assertIsNotNone(payload["pool_distribution"]["last_notified_key"])
        self.assertTrue(any("CRS pool distribution updated" in message for message in notifier.messages))

    def test_pool_distribution_http_failure_uses_browser_fallback(self):
        def http_provider(url):
            return SourcePayload(
                source_kind="http",
                source_url=url,
                fetched_at="2026-04-05T00:00:00Z",
                html=HTML_FIXTURE,
                rows=None,
                diagnostics={"status_code": 200},
            )

        def broken_pool_provider(url):
            raise RuntimeError("pool page unavailable")

        class DummyNotifier(object):
            def send(self, message):
                return NotificationResult(True, "dry_run", message, reason="dry_run")

        run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
            pool_distribution_provider=broken_pool_provider,
            pool_distribution_browser_provider=self._pool_distribution_browser_provider,
            notifier=DummyNotifier(),
        )

        with open(self.state_file, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        self.assertEqual(payload["pool_distribution"]["last_seen_key"], "unknown-date_bcb5657297fb5566")
