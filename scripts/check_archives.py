"""Read-only local archive preflight for the Inside Airbnb manifest."""
import argparse
import csv
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data_manifest.csv"
TYPES = {"listings", "calendar", "reviews"}

def main():
    parser = argparse.ArgumentParser(description="Verify local source archives without Snowflake.")
    parser.add_argument("--selection-file", help="Geographic selection JSON; applied to manifest")
    parser.add_argument("--country")
    parser.add_argument("--location")
    parser.add_argument("--snapshot")
    parser.add_argument("--files", nargs="+", choices=sorted(TYPES))
    parser.add_argument("--hash", action="store_true", help="Verify SHA-256 (slower).")
    args = parser.parse_args()
    selected = 0
    missing = []
    invalid = []
    total_bytes = 0
    with MANIFEST.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        if args.selection_file:
            from geography_selection import select_manifest_paths
            selected_paths = select_manifest_paths(rows, args.selection_file)
            rows = [row for row in rows if row["path"] in selected_paths]
        for row in rows:
            relative = Path(row["path"])
            parts = relative.parts
            if len(parts) != 6 or parts[:2] != ("data", "raw") or relative.name not in {f"{t}.csv.gz" for t in TYPES}:
                raise ValueError(f"Unexpected manifest path: {relative}")
            _, _, country, location, snapshot, filename = parts
            if args.country and country != args.country.strip().lower():
                continue
            if args.location and location != args.location.strip().lower():
                continue
            if args.snapshot and snapshot != args.snapshot:
                continue
            if args.files and filename not in {f"{t}.csv.gz" for t in args.files}:
                continue
            selected += 1
            path = ROOT / relative
            expected_size = int(row["size"])
            total_bytes += expected_size
            if not path.is_file():
                missing.append(relative.as_posix())
                continue
            if path.stat().st_size != expected_size:
                invalid.append(f"{relative}: size mismatch")
                continue
            if args.hash:
                digest = hashlib.sha256()
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest().lower() != row["sha256"].strip().lower():
                    invalid.append(f"{relative}: SHA-256 mismatch")
    print(f"Selected: {selected} archives / {total_bytes / 1024**3:.2f} GiB expected")
    print(f"Missing: {len(missing)}; invalid: {len(invalid)}")
    for entry in (missing + invalid)[:30]:
        print(" -", entry)
    if not selected:
        raise SystemExit("No matching manifest entries.")
    if missing or invalid:
        raise SystemExit(1)
    print("[OK] All selected archives verified" + (" (SHA-256)" if args.hash else " (size only)"))

if __name__ == "__main__":
    main()
