from pathlib import Path
from datetime import datetime
import csv
import gzip
import json
import os

import snowflake.connector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"

SNOWFLAKE_ACCOUNT = "JILNWYB-MO57208"
SNOWFLAKE_USER = "GGILLET"
SNOWFLAKE_ROLE = "INGESTION_ROLE"
SNOWFLAKE_WAREHOUSE = "DBT_WH"
SNOWFLAKE_DATABASE = "AIRBNB"
SNOWFLAKE_SCHEMA = "RAW"

FILE_TO_TABLE = {
    "listings.csv.gz": "RAW_LISTINGS",
    "calendar.csv.gz": "RAW_CALENDAR",
    "reviews.csv.gz": "RAW_REVIEWS",
}


def get_connection():
    password = os.getenv("DBT_SNOWFLAKE_PASSWORD")

    if not password:
        raise RuntimeError(
            "La variable DBT_SNOWFLAKE_PASSWORD est absente."
        )

    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=password,
        role=SNOWFLAKE_ROLE,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )


def discover_files():
    files = []

    for file_path in RAW_ROOT.rglob("*.csv.gz"):
        relative = file_path.relative_to(RAW_ROOT)

        # Structure attendue :
        # country / city / snapshot_date / filename
        if len(relative.parts) != 4:
            print(f"[SKIP] Structure inattendue : {relative}")
            continue

        country, city, snapshot_date, filename = relative.parts

        if filename not in FILE_TO_TABLE:
            print(f"[SKIP] Fichier non géré : {relative}")
            continue

        files.append(
            {
                "path": file_path,
                "country": country,
                "city": city,
                "snapshot_date": snapshot_date,
                "filename": filename,
                "target_table": FILE_TO_TABLE[filename],
            }
        )

    return sorted(
        files,
        key=lambda x: (
            x["country"],
            x["city"],
            x["snapshot_date"],
            x["filename"],
        ),
    )


def csv_gz_to_json_gz(source_path, destination_path):
    row_count = 0

    with gzip.open(
        source_path,
        "rt",
        encoding="utf-8",
        newline="",
    ) as source:
        reader = csv.DictReader(source)

        with gzip.open(
            destination_path,
            "wt",
            encoding="utf-8",
            newline="\n",
        ) as destination:

            for row in reader:
                destination.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                destination.write("\n")
                row_count += 1

    return row_count


def load_file(cursor, item):
    country = item["country"]
    city = item["city"]
    snapshot_date = item["snapshot_date"]
    filename = item["filename"]
    target_table = item["target_table"]
    source_path = item["path"]

    print("\n" + "=" * 100)
    print(
        f"{country} / {city} / {snapshot_date} / "
        f"{filename} -> {target_table}"
    )
    print("=" * 100)

    work_dir = PROJECT_ROOT / "target" / "ingestion"
    work_dir.mkdir(parents=True, exist_ok=True)

    json_filename = (
        f"{country}_{city}_{snapshot_date}_"
        f"{filename.replace('.csv.gz', '.json.gz')}"
    )

    json_path = work_dir / json_filename

    print("[1/5] Conversion CSV.GZ -> JSON.GZ")

    expected_rows = csv_gz_to_json_gz(
        source_path,
        json_path,
    )

    print(f"      {expected_rows:,} lignes converties")

    stage_path = (
        f"@AIRBNB.RAW.INSIDE_AIRBNB_STAGE/"
        f"{country}/{city}/{snapshot_date}"
    )

    print("[2/5] Upload vers le stage Snowflake")

    put_sql = (
        f"PUT 'file://{json_path.as_posix()}' "
        f"{stage_path} "
        f"AUTO_COMPRESS=FALSE "
        f"OVERWRITE=TRUE"
    )

    cursor.execute(put_sql)

    print("[3/5] Suppression du lot existant éventuel")

    cursor.execute(
        f"""
        DELETE FROM AIRBNB.RAW.{target_table}
        WHERE SOURCE_COUNTRY = %s
          AND SOURCE_CITY = %s
          AND SNAPSHOT_DATE = %s
          AND SOURCE_FILE = %s
        """,
        (
            country,
            city,
            snapshot_date,
            filename,
        ),
    )

    print("[4/5] Chargement dans la table RAW")

    copy_sql = f"""
        COPY INTO AIRBNB.RAW.{target_table}
        (
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            SOURCE_FILE,
            LOADED_AT,
            RAW_DATA
        )
        FROM (
            SELECT
                '{country}',
                '{city}',
                TO_DATE('{snapshot_date}'),
                '{filename}',
                CURRENT_TIMESTAMP(),
                $1
            FROM {stage_path}/{json_filename}
        )
        FILE_FORMAT = (
            TYPE = JSON
            COMPRESSION = GZIP
        )
        FORCE = TRUE
    """

    cursor.execute(copy_sql)

    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM AIRBNB.RAW.{target_table}
        WHERE SOURCE_COUNTRY = %s
          AND SOURCE_CITY = %s
          AND SNAPSHOT_DATE = %s
          AND SOURCE_FILE = %s
        """,
        (
            country,
            city,
            snapshot_date,
            filename,
        ),
    )

    loaded_rows = cursor.fetchone()[0]

    print("[5/5] Contrôle et journalisation")
    print(f"      attendu : {expected_rows:,}")
    print(f"      chargé  : {loaded_rows:,}")

    if loaded_rows != expected_rows:
        raise RuntimeError(
            f"Nombre de lignes incohérent pour {filename}: "
            f"{expected_rows:,} attendues, "
            f"{loaded_rows:,} chargées."
        )

    cursor.execute(
        """
        DELETE FROM AIRBNB.RAW.INGESTION_LOG
        WHERE SOURCE_COUNTRY = %s
          AND SOURCE_CITY = %s
          AND SNAPSHOT_DATE = %s
          AND SOURCE_FILE = %s
          AND TARGET_TABLE = %s
        """,
        (
            country,
            city,
            snapshot_date,
            filename,
            target_table,
        ),
    )

    cursor.execute(
        """
        INSERT INTO AIRBNB.RAW.INGESTION_LOG
        (
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            SOURCE_FILE,
            TARGET_TABLE,
            ROW_COUNT,
            LOADED_AT
        )
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP())
        """,
        (
            country,
            city,
            snapshot_date,
            filename,
            target_table,
            loaded_rows,
        ),
    )

    json_path.unlink(missing_ok=True)

    print("      OK")


def main():
    files = discover_files()

    print("=" * 100)
    print("INSIDE AIRBNB -> SNOWFLAKE RAW")
    print("=" * 100)
    print(f"Fichiers détectés : {len(files)}")

    for item in files:
        print(
            f"  {item['country']}/"
            f"{item['city']}/"
            f"{item['snapshot_date']}/"
            f"{item['filename']}"
        )

    if not files:
        raise RuntimeError("Aucun fichier source détecté.")

    connection = get_connection()

    try:
        cursor = connection.cursor()

        try:
            for item in files:
                load_file(cursor, item)

            connection.commit()

        finally:
            cursor.close()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print("\n" + "=" * 100)
    print("INGESTION TERMINEE")
    print("=" * 100)

if __name__ == "__main__":
    main()