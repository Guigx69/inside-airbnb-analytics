from pathlib import Path
import csv
import gzip
import json
import os

import snowflake.connector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"

SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PASSWORD = os.getenv("DBT_SNOWFLAKE_PASSWORD")

SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE", "INGESTION_ROLE")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "DBT_WH")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "AIRBNB")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "RAW")

FILE_TO_TABLE = {
    "listings.csv.gz": "RAW_LISTINGS",
    "calendar.csv.gz": "RAW_CALENDAR",
    "reviews.csv.gz": "RAW_REVIEWS",
}


def validate_environment():
    required = {
        "SNOWFLAKE_ACCOUNT": SNOWFLAKE_ACCOUNT,
        "SNOWFLAKE_USER": SNOWFLAKE_USER,
        "DBT_SNOWFLAKE_PASSWORD": SNOWFLAKE_PASSWORD,
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Variables d'environnement Snowflake manquantes : "
            + ", ".join(missing)
        )


def get_connection():
    validate_environment()

    return snowflake.connector.connect(
        account=SNOWFLAKE_ACCOUNT,
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        role=SNOWFLAKE_ROLE,
        warehouse=SNOWFLAKE_WAREHOUSE,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )


def qualified_table(table_name):
    return (
        f"{SNOWFLAKE_DATABASE}."
        f"{SNOWFLAKE_SCHEMA}."
        f"{table_name}"
    )


def stage_path(country, city, snapshot_date):
    return (
        f"@{SNOWFLAKE_DATABASE}."
        f"{SNOWFLAKE_SCHEMA}."
        f"INSIDE_AIRBNB_STAGE/"
        f"{country}/{city}/{snapshot_date}"
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

    target = qualified_table(target_table)
    ingestion_log = qualified_table("INGESTION_LOG")
    stage = stage_path(country, city, snapshot_date)

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

    print("[2/5] Upload vers le stage Snowflake")

    put_sql = (
        f"PUT 'file://{json_path.as_posix()}' "
        f"{stage} "
        f"AUTO_COMPRESS=FALSE "
        f"OVERWRITE=TRUE"
    )

    cursor.execute(put_sql)

    print("[3/5] Suppression du lot existant éventuel")

    cursor.execute(
        f"""
        DELETE FROM {target}
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
        COPY INTO {target}
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
            FROM {stage}/{json_filename}
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
        FROM {target}
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
        f"""
        DELETE FROM {ingestion_log}
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
        f"""
        INSERT INTO {ingestion_log}
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
    validate_environment()

    files = discover_files()

    print("=" * 100)
    print("INSIDE AIRBNB -> SNOWFLAKE RAW")
    print("=" * 100)

    print(
        f"Snowflake : "
        f"{SNOWFLAKE_ACCOUNT} / "
        f"{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}"
    )

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