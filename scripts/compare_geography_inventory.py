"""Compare selected live Inside Airbnb catalog paths with local manifest paths.

Read-only: fetches catalog metadata, never downloads archives or connects to Snowflake.
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from download_inside_airbnb import build_inventory, get_catalog
from geography_selection import select_datasets, select_manifest_paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-file", required=True)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be >= 0")

    live = select_datasets(build_inventory(get_catalog()), args.selection_file)
    live_paths = {item.manifest_path for item in live}
    manifest_path = ROOT / "data_manifest.csv"
    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    manifest_paths = select_manifest_paths(rows, args.selection_file)

    only_live = sorted(live_paths - manifest_paths)
    only_manifest = sorted(manifest_paths - live_paths)
    print(f"Live catalog:        {len(live_paths)} unique paths ({len(live)} records)")
    print(f"Selected manifest:   {len(manifest_paths)} unique paths")
    print(f"Shared paths:        {len(live_paths & manifest_paths)}")
    print(f"Only in live:        {len(only_live)}")
    print(f"Only in manifest:    {len(only_manifest)}")
    for title, paths in (("LIVE ONLY", only_live), ("MANIFEST ONLY", only_manifest)):
        print(f"\\n{title} (first {args.limit}):")
        for path in paths[:args.limit]:
            print("  " + path)
    print("\\n[READ-ONLY] No archives downloaded; no manifest or Snowflake changes.")


if __name__ == "__main__":
    main()
