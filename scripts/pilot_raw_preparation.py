"""Isolated Pacific Grove preparation pilot: never writes production RAW tables.

Uses a temporary Snowflake stage and temporary table in the current session.
Only accepts the fixed 130-row Pacific Grove Listings source.
"""
import argparse
import json
import tempfile
from pathlib import Path

from load_raw_to_snowflake import (
    load_manifest, get_connection, sha256_file, csv_gz_to_json_gz,
)

PILOT = "data/raw/united-states/pacific-grove/2026-03-31/listings.csv.gz"
STAGE = "V13_PILOT_PREP_STAGE"
TABLE = "V13_PILOT_PREP_RAW"


def main():
    parser = argparse.ArgumentParser(description="Isolated Snowflake PUT/COPY pilot")
    parser.add_argument("--execute", action="store_true",
                        help="Create TEMP objects and run PUT/COPY; default only checks local file")
    args = parser.parse_args()

    # Verify the selected file using the existing manifest loader, including size/hash.
    # Do not pass a filter Namespace: the loader validates every manifest item.
    # Select the pilot before calling the loader to avoid hashing all 1629 files.
    filters = argparse.Namespace(
        selection_file=None, country="united-states", location="pacific-grove",
        snapshot="2026-03-31", files=["listings"],
    )
    items = load_manifest(filters)
    matches = [x for x in items if x["relative_path"] == PILOT]
    if len(items) != 1 or len(matches) != 1:
        raise RuntimeError(f"Pilot selection must contain exactly {PILOT}; found {len(items)}")
    item = matches[0]
    print(f"LOCAL VERIFIED: {PILOT} sha256={item['sha256']} size={item['size']}")
    if not args.execute:
        print("READ-ONLY: pass --execute to use temporary Snowflake objects")
        return 0

    connection = get_connection()
    cursor = connection.cursor()
    try:
        with tempfile.TemporaryDirectory(prefix="v13_pilot_") as temp_dir:
            json_path = Path(temp_dir) / "listings_pilot.json.gz"
            expected = csv_gz_to_json_gz(item["path"], json_path)
            # Detect source modifications during conversion.
            if sha256_file(item["path"]) != item["sha256"]:
                raise RuntimeError("Source changed during conversion")
            if expected != 130:
                raise RuntimeError(f"Unexpected pilot row count: {expected}; expected 130")
            print(f"CONVERSION VERIFIED: {expected} rows")

            cursor.execute(f"CREATE TEMPORARY STAGE {STAGE}")
            cursor.execute(f"""
                CREATE TEMPORARY TABLE {TABLE} (
                    SOURCE_COUNTRY VARCHAR,
                    SOURCE_CITY VARCHAR,
                    SNAPSHOT_DATE DATE,
                    SOURCE_FILE VARCHAR,
                    LOADED_AT TIMESTAMP_LTZ,
                    RAW_DATA VARIANT
                )
            """)
            cursor.execute(
                f"PUT 'file://{json_path.as_posix()}' @{STAGE} "
                "AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
            )
            cursor.execute(f"""
                COPY INTO {TABLE}
                (SOURCE_COUNTRY, SOURCE_CITY, SNAPSHOT_DATE, SOURCE_FILE, LOADED_AT, RAW_DATA)
                FROM (
                    SELECT %s, %s, TO_DATE(%s), %s, CURRENT_TIMESTAMP(), $1
                    FROM @{STAGE}/listings_pilot.json.gz
                )
                FILE_FORMAT=(TYPE=JSON COMPRESSION=GZIP)
                FORCE=TRUE
                ON_ERROR=ABORT_STATEMENT
            """, ("united-states", "pacific-grove", "2026-03-31", "listings.csv.gz"))
            cursor.execute(f"""
                SELECT COUNT(*),
                       COUNT_IF(SOURCE_COUNTRY='united-states'
                           AND SOURCE_CITY='pacific-grove'
                           AND SNAPSHOT_DATE=TO_DATE('2026-03-31')
                           AND SOURCE_FILE='listings.csv.gz'),
                       COUNT_IF(RAW_DATA IS NOT NULL)
                FROM {TABLE}
            """)
            actual, correct_metadata, populated = map(int, cursor.fetchone())
            if (actual, correct_metadata, populated) != (130, 130, 130):
                raise RuntimeError(
                    f"FAIL: count={actual}, metadata={correct_metadata}, raw_data={populated}"
                )
            print("PASS: 130 rows; 130 metadata matches; 130 non-null RAW_DATA")
            print("Temporary Snowflake stage/table will be removed on session close")
    finally:
        cursor.close()
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
