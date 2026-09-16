from pathlib import Path
import csv
import gzip
from collections import Counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SNAPSHOT_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "france"
    / "lyon"
    / "2025-09-18"
)


def analyse_keys(filename, key_columns):
    file_path = SNAPSHOT_PATH / filename

    print("\n" + "=" * 90)
    print(f"FILE : {filename}")
    print(f"CLE CANDIDATE : {', '.join(key_columns)}")
    print("=" * 90)

    keys = Counter()
    row_count = 0

    with gzip.open(file_path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            row_count += 1
            key = tuple(row[column] for column in key_columns)
            keys[key] += 1

    duplicate_keys = {
        key: count
        for key, count in keys.items()
        if count > 1
    }

    duplicate_rows = sum(
        count - 1
        for count in duplicate_keys.values()
    )

    print(f"Nombre de lignes       : {row_count:,}")
    print(f"Nombre de cles uniques : {len(keys):,}")
    print(f"Cles dupliquees        : {len(duplicate_keys):,}")
    print(f"Lignes en doublon      : {duplicate_rows:,}")

    if duplicate_keys:
        print("\nExemples de doublons :")

        for key, count in list(duplicate_keys.items())[:10]:
            print(f"  {key} -> {count} occurrences")

    else:
        print("RESULTAT                : CLE UNIQUE")

def inspect_review_duplicates():
    file_path = SNAPSHOT_PATH / "reviews.csv.gz"

    rows_by_id = {}

    with gzip.open(file_path, "rt", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            review_id = row["id"]
            rows_by_id.setdefault(review_id, []).append(row)

    print("\n" + "=" * 90)
    print("DETAIL DES REVIEW_ID DUPLIQUES")
    print("=" * 90)

    for review_id, rows in rows_by_id.items():
        if len(rows) <= 1:
            continue

        identical = all(row == rows[0] for row in rows[1:])

        print(f"\nreview_id : {review_id}")
        print(f"Occurrences : {len(rows)}")
        print(f"Doublon strictement identique : {identical}")

        for i, row in enumerate(rows, start=1):
            print(f"\n  Occurrence {i}")
            print(f"    listing_id   : {row['listing_id']}")
            print(f"    date         : {row['date']}")
            print(f"    reviewer_id  : {row['reviewer_id']}")
            print(f"    reviewer_name: {row['reviewer_name']}")
            print(f"    comments     : {row['comments'][:200]}")

def main():
    analyse_keys(
        "listings.csv.gz",
        ["id"]
    )

    analyse_keys(
        "calendar.csv.gz",
        ["listing_id", "date"]
    )

    analyse_keys(
        "reviews.csv.gz",
        ["id"]
    )

    inspect_review_duplicates()

if __name__ == "__main__":
    main()