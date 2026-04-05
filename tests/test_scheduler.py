import os
import tempfile
import unittest

from ircc_draw_automation.browser_source import fetch_browser_source
from ircc_draw_automation.models import SourcePayload
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


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.tempdir.name, "state.json")
        self.fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "browser_rows_fixture.json")

    def tearDown(self):
        self.tempdir.cleanup()

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
        )

        self.assertEqual(result.reason, "http_failed_browser_used")
        self.assertEqual(result.source_kind, "browser")
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
        )

        self.assertEqual(result.reason, "http_failed_browser_used")
        self.assertEqual(result.latest_draw.draw_key, "2026-04-02_408")

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

        first_result = run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
        )
        second_result = run_check(
            state_file=self.state_file,
            dry_run=False,
            http_provider=http_provider,
            browser_provider=None,
        )

        self.assertTrue(first_result.state_updated)
        self.assertTrue(os.path.exists(self.state_file))
        self.assertFalse(second_result.changed)
        self.assertEqual(second_result.change_status, "draw_already_seen")

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
        )

        self.assertFalse(result.state_updated)
        self.assertFalse(os.path.exists(self.state_file))
