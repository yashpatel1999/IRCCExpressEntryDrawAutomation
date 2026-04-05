import unittest

from ircc_draw_automation import browser_source


class BrowserSourceTests(unittest.TestCase):
    def test_live_mcp_payload_is_normalized(self):
        original = browser_source.capture_draw_rows_via_mcp
        try:
            browser_source.capture_draw_rows_via_mcp = lambda url: {
                "source_url": url,
                "captured_at": "2026-04-05T00:00:00Z",
                "headers": ["Round", "Date", "Program", "Invitations issued", "CRS score of lowest-ranked candidate invited"],
                "rows": [["408", "April 2, 2026", "Trades Occupations, 2026-Version 3", "3,000", "477"]],
            }

            payload = browser_source.fetch_browser_source(url="https://example.com")

            self.assertEqual(payload.source_kind, "mcp_browser")
            self.assertEqual(payload.rows[0]["draw_number"], "408")
            self.assertEqual(payload.rows[0]["draw_date"], "April 2, 2026")
        finally:
            browser_source.capture_draw_rows_via_mcp = original

    def test_live_header_aliases_are_supported(self):
        original = browser_source.capture_draw_rows_via_mcp
        try:
            browser_source.capture_draw_rows_via_mcp = lambda url: {
                "source_url": url,
                "captured_at": "2026-04-05T00:00:00Z",
                "headers": ["#", "Date", "Round type", "Invitations issued", "CRS score of lowest-ranked candidate invited"],
                "rows": [["408", "April 2, 2026", "Trades Occupations, 2026-Version 3", "3,000", "477"]],
            }

            payload = browser_source.fetch_browser_source(url="https://example.com")

            self.assertEqual(payload.rows[0]["draw_number"], "408")
            self.assertEqual(payload.rows[0]["program"], "Trades Occupations, 2026-Version 3")
        finally:
            browser_source.capture_draw_rows_via_mcp = original
