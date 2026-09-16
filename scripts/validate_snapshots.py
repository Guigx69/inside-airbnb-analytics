from pathlib import Path
import csv
import gzip
from collections import Counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LYON_PATH = PROJECT_ROOT / "data" / "raw" / "france" / "lyon"

SNAPSHOTS = [
    "2025-09-18",
    "2025-12-22",
    "2026-03-25",
    "2026-06-22",
]

FILES = {
    "listings.csv.gz": ["id"],
    "calendar.csv.gz": ["listing_id", "date"],
    "reviews.csv.gz": ["listing_id", "id"],
}


def read_header(file_path):
    with gzip.open(file_path, "rt", encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


def analyse_file(file_path, key_columns):
    row_count = 0
    keys = Counter()

    with gzip.open(file_path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            row_count += 1
            key = tuple(row[column] for column in key_columns)
            keys[key] += 1

    duplicate_keys = sum(
        1 for count in keys.values() if count > 1
    )

    duplicate_rows = sum(
        count - 1 for count in keys.values() if count > 1
    )

    return {
        "rows": row_count,
        "unique_keys": len(keys),
        "duplicate_keys": duplicate_keys,
        "duplicate_rows": duplicate_rows,
    }


def main():
    print("=" * 110)
    print("VALIDATION MULTI-SNAPSHOTS - LYON")
    print("=" * 110)

    reference_headers = {}

    for filename in FILES:
        reference_path = LYON_PATH / SNAPSHOTS[0] / filename
        reference_headers[filename] = read_header(reference_path)

    for snapshot in SNAPSHOTS:
        print("\n" + "#" * 110)
        print(f"SNAPSHOT : {snapshot}")
        print("#" * 110)

        snapshot_path = LYON_PATH / snapshot

        for filename, key_columns in FILES.items():
            file_path = snapshot_path / filename

            if not file_path.exists():
                print(f"\n[ERREUR] {filename} absent")
                continue

            header = read_header(file_path)
            reference_header = reference_headers[filename]

            added_columns = [
                col for col in header
                if col not in reference_header
            ]

            removed_columns = [
                col for col in reference_header
                if col not in header
            ]

            same_order = header == reference_header

            stats = analyse_file(file_path, key_columns)

            print(f"\n{filename}")
            print("-" * 110)
            print(f"Colonnes              : {len(header)}")
            print(f"Schema identique      : {header == reference_header}")
            print(f"Ordre identique       : {same_order}")
            print(f"Colonnes ajoutees     : {added_columns or 'Aucune'}")
            print(f"Colonnes supprimees   : {removed_columns or 'Aucune'}")
            print(f"Lignes                : {stats['rows']:,}")
            print(f"Cles uniques          : {stats['unique_keys']:,}")
            print(f"Cles dupliquees       : {stats['duplicate_keys']:,}")
            print(f"Lignes en doublon     : {stats['duplicate_rows']:,}")

if __name__ == "__main__":
    main()