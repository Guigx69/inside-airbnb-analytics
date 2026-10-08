"""Safely orchestrate Inside Airbnb collection, archive checks, RAW loading and dbt.

Default is a read-only preview. Use --execute --sync to permit downloads and
RAW writes. dbt build is opt-in with --dbt-build; no automatic destructive reset.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def commands(selection_file: str, execute: bool, sync: bool, dbt_build: bool,
             python_executable: str = sys.executable) -> list[tuple[str, list[str]]]:
    collector = [python_executable, str(ROOT / "scripts" / "download_inside_airbnb.py"),
                 "--selection-file", selection_file]
    if execute and sync:
        collector += ["--sync", "--verify"]
    else:
        collector += ["--dry-run", "--verify"]

    steps = [("collector", collector)]
    if not execute or sync:
        # A live-catalog preview can reference not-yet-downloaded archives.
        # On an executing sync, every newly published archive is fetched first.
        pass
    steps.append(("archives", [python_executable, str(ROOT / "scripts" / "check_archives.py"),
                               "--selection-file", selection_file, "--hash"]))
    raw = [python_executable, str(ROOT / "scripts" / "load_raw_to_snowflake.py"),
           "--selection-file", selection_file]
    if not execute:
        raw.append("--dry-run")
    steps.append(("raw", raw))
    if execute and dbt_build:
        steps.append(("dbt", ["dbt", "build", "--project-dir", str(ROOT)]))
    return steps


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-file", default="config/geography.example.json")
    parser.add_argument("--execute", action="store_true", help="Allow RAW writes")
    parser.add_argument("--sync", action="store_true", help="Download missing archives (requires --execute)")
    parser.add_argument("--dbt-build", action="store_true", help="Run dbt build (requires --execute)")
    args = parser.parse_args(argv)
    if (args.sync or args.dbt_build) and not args.execute:
        parser.error("--sync and --dbt-build require --execute")
    selection = Path(args.selection_file)
    if not selection.is_absolute():
        selection = ROOT / selection
    if not selection.is_file():
        parser.error(f"Selection file not found: {selection}")
    args.selection_file = str(selection)
    return args


def main(argv=None, runner=subprocess.run):
    args = parse_args(argv)
    steps = commands(args.selection_file, args.execute, args.sync, args.dbt_build)
    print("Mode:", "EXECUTE" if args.execute else "PREVIEW (no writes)", flush=True)
    print("Sync:", args.sync, "dbt build:", args.dbt_build, flush=True)
    for index, (name, cmd) in enumerate(steps, 1):
        print(f"[{index}/{len(steps)}] {name}: {' '.join(cmd)}", flush=True)
        result = runner(cmd, cwd=ROOT, check=False)
        if result.returncode:
            print(f"[FAILED] {name}: exit code {result.returncode}; stopping pipeline", file=sys.stderr)
            return result.returncode
    print("[OK] All requested steps completed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
