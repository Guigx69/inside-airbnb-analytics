"""Regression tests for safe explicit geographic selection (offline)."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_pipeline", ROOT / "scripts" / "run_pipeline.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestSelectionPreflight(unittest.TestCase):
    def test_missing_selection_is_rejected(self):
        with self.assertRaises(SystemExit) as exc:
            module.parse_args([])
        self.assertEqual(exc.exception.code, 2)

    def test_unknown_selection_is_rejected(self):
        with self.assertRaises(SystemExit) as exc:
            module.parse_args(["--selection-file", "config/does-not-exist.json"])
        self.assertEqual(exc.exception.code, 2)

    def test_sync_requires_execute(self):
        with self.assertRaises(SystemExit) as exc:
            module.parse_args(["--selection-file", "config/geography.lyon.example.json", "--sync"])
        self.assertEqual(exc.exception.code, 2)

    def test_valid_explicit_selection_previews(self):
        args = module.parse_args(["--selection-file", "config/geography.lyon.example.json"])
        self.assertFalse(args.execute)
        self.assertTrue(Path(args.selection_file).is_file())
        steps = module.commands(args.selection_file, args.execute, args.sync, args.dbt_build)
        self.assertEqual([name for name, _ in steps], ["collector", "archives", "raw"])
        self.assertIn("--dry-run", steps[0][1])
        self.assertIn("--dry-run", steps[2][1])


if __name__ == "__main__":
    unittest.main()
