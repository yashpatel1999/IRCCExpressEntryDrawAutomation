import unittest

from ircc_draw_automation.enricher import build_pool_distribution_message
from ircc_draw_automation.models import PoolDistributionRecord


class EnricherTests(unittest.TestCase):
    def test_build_pool_distribution_message_includes_highlight_rows(self):
        record = PoolDistributionRecord(
            distribution_key="2026-03-29_hash",
            distribution_date="2026-03-29",
            total_candidates=230186,
            rows=[
                {"range_label": "601-1200", "candidate_count": 351},
                {"range_label": "501-600", "candidate_count": 11648},
                {"range_label": "451-500", "candidate_count": 73445},
                {"range_label": "Total", "candidate_count": 230186},
            ],
            source_url="https://example.com",
            fetched_at="2026-04-05T00:00:00Z",
            content_hash="sha256:test",
        )

        message = build_pool_distribution_message(record)

        self.assertIn("IRCC CRS pool distribution updated (2026-03-29)", message)
        self.assertIn("Total candidates: 230186", message)
        self.assertIn("601-1200: 351", message)
        self.assertIn("501-600: 11648", message)
        self.assertIn("451-500: 73445", message)
        self.assertNotIn("Total: 230186", message)

