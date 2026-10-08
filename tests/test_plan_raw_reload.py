"""Unit tests for the read-only RAW reload classifier; no Snowflake connection."""
import sys
import types
import unittest
from pathlib import Path

# Snowflake connector is imported by the ingestion module, but never used here.
# Production environments already install it; no mocking of database behavior needed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from plan_raw_reload import classify
from load_raw_to_snowflake import ingestion_key


class ReloadClassificationTests(unittest.TestCase):
    def setUp(self):
        self.item = {
            "country": "argentina", "location": "buenos-aires",
            "snapshot_date": "2026-03-30", "filename": "listings.csv.gz",
            "target_table": "RAW_LISTINGS", "sha256": "a" * 64,
        }
        self.key = ingestion_key(self.item)

    def status(self, log=None, inventory=None):
        return classify(self.item, log or {}, inventory or {})[0]

    def test_new_file(self):
        self.assertEqual(self.status(), "NEW")

    def test_orphan_raw(self):
        self.assertEqual(self.status(inventory={self.key: 3}), "BLOCKED_RAW_ORPHAN")

    def test_missing_raw(self):
        self.assertEqual(self.status(log={self.key: {"row_count": 3, "sha256": "a" * 64}}),
                         "BLOCKED_COUNT_MISMATCH")

    def test_row_count_mismatch(self):
        self.assertEqual(self.status(log={self.key: {"row_count": 3, "sha256": "a" * 64}},
                                     inventory={self.key: 2}), "BLOCKED_COUNT_MISMATCH")

    def test_legacy_without_hash(self):
        self.assertEqual(self.status(log={self.key: {"row_count": 3, "sha256": None}},
                                     inventory={self.key: 3}), "LEGACY_UNCERTIFIED")

    def test_unchanged_hash_case_insensitive(self):
        self.item["sha256"] = "ab" * 32
        self.assertEqual(self.status(log={self.key: {"row_count": 3, "sha256": "AB" * 32}},
                                     inventory={self.key: 3}), "UNCHANGED")

    def test_changed_hash(self):
        self.assertEqual(self.status(log={self.key: {"row_count": 3, "sha256": "b" * 64}},
                                     inventory={self.key: 3}), "RELOAD_CANDIDATE")

    def test_empty_existing_file_with_matching_hash(self):
        self.assertEqual(self.status(log={self.key: {"row_count": 0, "sha256": "a" * 64}}),
                         "UNCHANGED")

    def test_empty_existing_file_without_hash(self):
        self.assertEqual(self.status(log={self.key: {"row_count": 0, "sha256": None}}),
                         "LEGACY_UNCERTIFIED")

    def test_empty_raw_orphan_not_distinguishable_from_new(self):
        # A zero-row RAW lot leaves no physical inventory entry.
        # Without an INGESTION_LOG row, the classifier cannot distinguish it from NEW.
        self.assertEqual(self.status(), "NEW")


if __name__ == "__main__":
    unittest.main()
