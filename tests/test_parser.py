import os
import unittest

from ircc_draw_automation.browser_source import fetch_browser_source
from ircc_draw_automation.parser import parse_latest_draw_from_html, parse_latest_draw_from_rows


SAMPLE_HTML = """
<html>
  <body>
    <main>
      <table>
        <tbody>
          <tr>
            <td>Express Entry round #341</td>
            <td>March 20, 2026</td>
            <td>Canadian Experience Class</td>
            <td>Invitations issued: 7,500</td>
            <td>CRS score of lowest-ranked candidate invited: 515</td>
          </tr>
        </tbody>
      </table>
    </main>
  </body>
</html>
"""


TABLE_WITH_HEADER_HTML = """
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
            <td>March 20, 2026</td>
            <td>Canadian Experience Class</td>
            <td>7,500</td>
            <td>515</td>
          </tr>
        </tbody>
      </table>
    </main>
  </body>
</html>
"""


MULTI_ROW_HTML = """
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


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "browser_rows_fixture.json")


class ParserTests(unittest.TestCase):
    def test_parse_latest_draw_from_html_extracts_expected_fields(self):
        parsed = parse_latest_draw_from_html(
            html=SAMPLE_HTML,
            source_url="https://example.com/express-entry-rounds.html",
        )

        self.assertEqual(parsed.draw_key, "2026-03-20_341")
        self.assertEqual(parsed.draw_number, 341)
        self.assertEqual(parsed.draw_date, "2026-03-20")
        self.assertEqual(parsed.program, "Canadian Experience Class")
        self.assertEqual(parsed.invitations, 7500)
        self.assertEqual(parsed.crs_cutoff, 515)

    def test_parse_latest_draw_prefers_table_body_row_over_header_labels(self):
        parsed = parse_latest_draw_from_html(
            html=TABLE_WITH_HEADER_HTML,
            source_url="https://example.com/express-entry-rounds.html",
        )

        self.assertEqual(parsed.draw_key, "2026-03-20_341")
        self.assertEqual(parsed.draw_number, 341)
        self.assertEqual(parsed.draw_date, "2026-03-20")
        self.assertEqual(parsed.program, "Canadian Experience Class")
        self.assertEqual(parsed.invitations, 7500)
        self.assertEqual(parsed.crs_cutoff, 515)

    def test_parse_latest_draw_selects_highest_draw_number(self):
        parsed = parse_latest_draw_from_html(
            html=MULTI_ROW_HTML,
            source_url="https://example.com/express-entry-rounds.html",
        )

        self.assertEqual(parsed.draw_key, "2026-04-02_408")
        self.assertEqual(parsed.draw_number, 408)
        self.assertEqual(parsed.draw_date, "2026-04-02")
        self.assertEqual(parsed.program, "Trades Occupations, 2026-Version 3")
        self.assertEqual(parsed.invitations, 3000)
        self.assertEqual(parsed.crs_cutoff, 477)

    def test_parse_latest_draw_from_browser_rows_handles_programs_outside_known_list(self):
        payload = fetch_browser_source(fixture_path=FIXTURE_PATH)
        parsed = parse_latest_draw_from_rows(payload.rows, payload.source_url)

        self.assertEqual(parsed.draw_key, "2026-04-02_408")
        self.assertEqual(parsed.draw_number, 408)
        self.assertEqual(parsed.draw_date, "2026-04-02")
        self.assertEqual(parsed.program, "Trades Occupations, 2026-Version 3")
        self.assertEqual(parsed.invitations, 3000)
        self.assertEqual(parsed.crs_cutoff, 477)
