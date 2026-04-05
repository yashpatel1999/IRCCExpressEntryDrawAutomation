import unittest
from datetime import datetime

from ircc_draw_automation.models import DrawRecord
from ircc_draw_automation.validator import validate_draw_record


class ValidatorTests(unittest.TestCase):
    def test_valid_recent_record_passes(self):
        record = DrawRecord(
            draw_key="2026-04-02_408",
            draw_number=408,
            draw_date="2026-04-02",
            program="Trades Occupations, 2026-Version 3",
            invitations=3000,
            crs_cutoff=477,
            tie_breaking=None,
            source_url="https://example.com",
            fetched_at="2026-04-05T00:00:00Z",
            content_hash="sha256:test",
        )

        result = validate_draw_record(record, now=datetime(2026, 4, 5))

        self.assertTrue(result.is_valid)
        self.assertEqual(result.reason, "valid")
        self.assertGreater(result.confidence, 0.0)

    def test_stale_record_fails(self):
        record = DrawRecord(
            draw_key="2025-03-21_341",
            draw_number=341,
            draw_date="2025-03-21",
            program="French language proficiency (Version 1)",
            invitations=7500,
            crs_cutoff=379,
            tie_breaking=None,
            source_url="https://example.com",
            fetched_at="2026-04-05T00:00:00Z",
            content_hash="sha256:test",
        )

        result = validate_draw_record(record, now=datetime(2026, 4, 5), max_age_days=60)

        self.assertFalse(result.is_valid)
        self.assertTrue(result.reason.startswith("stale_draw_date"))

    def test_missing_fields_fail(self):
        record = DrawRecord(
            draw_key="2026-04-02_408",
            draw_number=408,
            draw_date="2026-04-02",
            program=None,
            invitations=None,
            crs_cutoff=477,
            tie_breaking=None,
            source_url="https://example.com",
            fetched_at="2026-04-05T00:00:00Z",
            content_hash="sha256:test",
        )

        result = validate_draw_record(record, now=datetime(2026, 4, 5))

        self.assertFalse(result.is_valid)
        self.assertTrue(result.reason.startswith("missing_fields"))
