"""Offline orchestration contract tests; no network or Snowflake required."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_pipeline


class PipelineTests(unittest.TestCase):
    def test_preview_is_read_only(self):
        steps = run_pipeline.commands("scope.json", False, False, False)
        self.assertEqual([name for name, _ in steps], ["collector", "archives", "raw"])
        self.assertIn("--dry-run", steps[0][1])
        self.assertIn("--dry-run", steps[2][1])
        self.assertIn("--hash", steps[1][1])

    def test_execute_sync_and_dbt(self):
        steps = run_pipeline.commands("scope.json", True, True, True)
        self.assertEqual([name for name, _ in steps], ["collector", "archives", "raw", "dbt"])
        self.assertIn("--sync", steps[0][1])
        self.assertNotIn("--dry-run", steps[2][1])
        self.assertEqual(steps[3][1][1], "build")
        self.assertTrue(steps[3][1][0] == "dbt" or steps[3][1][0].endswith("dbt.exe"))

    def test_stop_on_failure(self):
        calls = []
        def runner(cmd, **kwargs):
            calls.append(cmd)
            return SimpleNamespace(returncode=7 if len(calls) == 2 else 0)
        with patch.object(run_pipeline, "parse_args", return_value=SimpleNamespace(
            selection_file="scope.json", execute=False, sync=False, dbt_build=False)):
            self.assertEqual(run_pipeline.main(runner=runner), 7)
        self.assertEqual(len(calls), 2)

    def test_unsafe_flags_rejected(self):
        for flag in ("--sync", "--dbt-build"):
            with self.subTest(flag=flag), self.assertRaises(SystemExit):
                run_pipeline.parse_args([flag])


if __name__ == "__main__":
    unittest.main()
