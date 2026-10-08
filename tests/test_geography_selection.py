"""Offline regression tests for geographic selection of local manifests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from geography_selection import select_datasets, select_manifest_paths


class GeographySelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "selection.json"
        self.rows = [
            {"path": "data/raw/france/lyon/2026-06-22/listings.csv.gz"},
            {"path": "data/raw/france/paris/2026-06-22/reviews.csv.gz"},
            {"path": "data/raw/japan/tokyo/2026-06-30/calendar.csv.gz"},
            {"path": "data/raw/australia/sydney/2026-06-16/listings.csv.gz"},
        ]

    def write(self, payload):
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def test_union_and_exclusion(self):
        self.write({"include": {"continents": ["Europe"], "countries": ["Japan"], "cities": ["Sydney"]}, "exclude": {"cities": ["Paris"]}})
        actual = select_manifest_paths(self.rows, self.path)
        self.assertEqual(actual, {self.rows[i]["path"] for i in (0, 2, 3)})

    def test_overlap_does_not_duplicate(self):
        self.write({"include": {"continents": ["Europe"], "countries": ["France"], "cities": ["Lyon"]}})
        actual = select_manifest_paths(self.rows, self.path)
        self.assertEqual(len(actual), 2)

    def test_unknown_city_fails_closed(self):
        self.write({"include": {"cities": ["Atlantis"]}})
        with self.assertRaisesRegex(ValueError, "Unknown cities"):
            select_manifest_paths(self.rows, self.path)

    def test_empty_inclusion_rejected(self):
        self.write({"include": {}})
        with self.assertRaisesRegex(ValueError, "At least one inclusion"):
            select_manifest_paths(self.rows, self.path)

    def test_invalid_manifest_path_rejected(self):
        self.write({"include": {"countries": ["France"]}})
        with self.assertRaisesRegex(ValueError, "Unexpected manifest path"):
            select_manifest_paths([{"path": "../outside.csv.gz"}], self.path)

    def test_selection_does_not_require_network(self):
        self.write({"include": {"countries": ["France"]}})
        self.assertEqual(len(select_manifest_paths(self.rows, self.path)), 2)


if __name__ == "__main__":
    unittest.main()
