from pathlib import Path
import csv
import gzip
import argparse
import json
import os
import hashlib

import snowflake.connector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"
MANIFEST_PATH = PROJECT_ROOT / "data_manifest.csv"

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


def stage_path(country, location, snapshot_date):
    return (
        f"@{SNOWFLAKE_DATABASE}."
        f"{SNOWFLAKE_SCHEMA}."
        f"INSIDE_AIRBNB_STAGE/"
        f"{country}/{location}/{snapshot_date}"
    )

def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()

def load_manifest(args=None):
    if not MANIFEST_PATH.exists():
        raise RuntimeError(
            f"Manifest introuvable : {MANIFEST_PATH}"
        )

    items = []

    with MANIFEST_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        required_columns = {
            "path",
            "size",
            "sha256",
        }

        if not reader.fieldnames:
            raise RuntimeError("Manifest vide ou invalide.")

        missing_columns = required_columns - set(reader.fieldnames)

        if missing_columns:
            raise RuntimeError(
                "Colonnes manquantes dans le manifest : "
                + ", ".join(sorted(missing_columns))
            )

        rows = list(reader)
        if args is not None and args.selection_file:
            from geography_selection import select_manifest_paths
            selected_paths = select_manifest_paths(rows, args.selection_file)
            rows = [row for row in rows if row["path"] in selected_paths]

        for row in rows:
            relative_path = Path(row["path"])

            # Structure attendue :
            # data/raw/country/location/snapshot_date/filename
            parts = relative_path.parts

            if len(parts) != 6:
                raise RuntimeError(
                    f"Chemin inattendu dans le manifest : "
                    f"{relative_path}"
                )

            data_dir, raw_dir, country, location, snapshot_date, filename = parts

            if data_dir != "data" or raw_dir != "raw":
                raise RuntimeError(
                    f"Chemin hors data/raw dans le manifest : "
                    f"{relative_path}"
                )

            if filename not in FILE_TO_TABLE:
                continue

            if args is not None:
                if args.country and country.lower() != args.country.strip().lower():
                    continue
                if args.location and location.lower() != args.location.strip().lower():
                    continue
                if args.snapshot and snapshot_date != args.snapshot:
                    continue
                if args.files and filename not in {
                    f"{dataset}.csv.gz" for dataset in args.files
                }:
                    continue

            source_path = PROJECT_ROOT / relative_path

            if not source_path.exists():
                raise RuntimeError(
                    f"Fichier du manifest absent localement : "
                    f"{relative_path}"
                )

            actual_size = source_path.stat().st_size
            expected_size = int(row["size"])

            if actual_size != expected_size:
                raise RuntimeError(
                    f"Taille incohérente pour {relative_path}: "
                    f"{expected_size} attendus, "
                    f"{actual_size} trouvés."
                )

            expected_sha256 = row["sha256"].strip().lower()

            if len(expected_sha256) != 64:
                raise RuntimeError(
                    f"SHA-256 invalide dans le manifest pour "
                    f"{relative_path}: {expected_sha256}"
                )

            actual_sha256 = sha256_file(source_path)

            if actual_sha256 != expected_sha256:
                raise RuntimeError(
                    f"SHA-256 incohérent pour {relative_path}:\n"
                    f"manifest : {expected_sha256}\n"
                    f"fichier  : {actual_sha256}"
                )

            items.append(
                {
                    "path": source_path,
                    "relative_path": relative_path.as_posix(),
                    "country": country,
                    "location": location,
                    "snapshot_date": snapshot_date,
                    "filename": filename,
                    "target_table": FILE_TO_TABLE[filename],
                    "size": expected_size,
                    "sha256": expected_sha256,
                }
            )

    return sorted(
        items,
        key=lambda x: (
            x["country"],
            x["location"],
            x["snapshot_date"],
            x["filename"],
        ),
    )


def get_ingestion_log(cursor):
    ingestion_log = qualified_table("INGESTION_LOG")

    cursor.execute(
        f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            TO_CHAR(SNAPSHOT_DATE, 'YYYY-MM-DD'),
            SOURCE_FILE,
            TARGET_TABLE,
            ROW_COUNT
        FROM {ingestion_log}
        """
    )

    loaded = {}

    for (
        country,
        location,
        snapshot_date,
        source_file,
        target_table,
        row_count,
    ) in cursor.fetchall():
        key = (
            country,
            location,
            snapshot_date,
            source_file,
            target_table,
        )

        if key in loaded:
            raise RuntimeError(
                "Doublon détecté dans INGESTION_LOG : "
                + " / ".join(str(value) for value in key)
            )

        loaded[key] = int(row_count)

    return loaded


def ingestion_key(item):
    return (
        item["country"],
        item["location"],
        item["snapshot_date"],
        item["filename"],
        item["target_table"],
    )

def get_raw_row_count(cursor, item):
    """
    Contrôle ciblé utilisé après le chargement d'un nouveau fichier.

    On conserve volontairement ce COUNT(*) unitaire :
    il valide le lot qui vient d'être chargé avant son COMMIT.
    """
    target = qualified_table(item["target_table"])

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
            item["country"],
            item["location"],
            item["snapshot_date"],
            item["filename"],
        ),
    )

    return int(cursor.fetchone()[0])


def get_raw_inventory(cursor):
    """
    Construit l'inventaire des lots présents dans RAW.

    Une seule agrégation est exécutée par table RAW :
      - RAW_LISTINGS
      - RAW_CALENDAR
      - RAW_REVIEWS

    La clé retournée est identique à ingestion_key():
      (
          country,
          location,
          snapshot_date,
          source_file,
          target_table,
      )
    """
    inventory = {}

    for target_table in sorted(set(FILE_TO_TABLE.values())):
        target = qualified_table(target_table)

        print(f"  [RAW] Inventaire groupé de {target_table}...")

        cursor.execute(
            f"""
            SELECT
                SOURCE_COUNTRY,
                SOURCE_CITY,
                TO_CHAR(SNAPSHOT_DATE, 'YYYY-MM-DD'),
                SOURCE_FILE,
                COUNT(*)
            FROM {target}
            GROUP BY
                SOURCE_COUNTRY,
                SOURCE_CITY,
                SNAPSHOT_DATE,
                SOURCE_FILE
            """
        )

        for (
            country,
            location,
            snapshot_date,
            source_file,
            row_count,
        ) in cursor.fetchall():
            key = (
                country,
                location,
                snapshot_date,
                source_file,
                target_table,
            )

            if key in inventory:
                raise RuntimeError(
                    "Doublon logique détecté dans l'inventaire RAW : "
                    + " / ".join(str(value) for value in key)
                )

            inventory[key] = int(row_count)

    return inventory


def classify_files(cursor, files, ingestion_log):
    pending = []
    skipped = []

    print("\nContrôle des fichiers déjà chargés...")
    print("Construction de l'inventaire RAW groupé...")

    raw_inventory = get_raw_inventory(cursor)

    manifest_keys = {
        ingestion_key(item)
        for item in files
    }

    #
    # Sécurité 1 :
    # tout lot journalisé doit réellement exister dans RAW
    # avec exactement le nombre de lignes journalisé.
    #
    for key, logged_rows in ingestion_log.items():
        actual_rows = raw_inventory.get(key)

        # Un lot source vide est légitimement journalisé avec 0 ligne.
        # Il ne peut pas apparaître dans l'inventaire RAW construit
        # par GROUP BY puisqu'aucune ligne physique n'existe.
        if actual_rows is None and logged_rows == 0:
            continue

        if actual_rows is None:
            raise RuntimeError(
                "\nIncohérence RAW / INGESTION_LOG :\n"
                f"lot journalisé absent de RAW : "
                f"{' / '.join(str(value) for value in key)}"
            )

        if actual_rows != logged_rows:
            raise RuntimeError(
                "\nIncohérence RAW / INGESTION_LOG :\n"
                f"{' / '.join(str(value) for value in key)}\n"
                f"INGESTION_LOG : {logged_rows:,} lignes\n"
                f"RAW           : {actual_rows:,} lignes\n"
                "Chargement interrompu pour éviter une "
                "modification automatique des données."
            )

    #
    # Sécurité 2 :
    # si RAW contient un lot correspondant au manifest mais que
    # INGESTION_LOG ne le connaît pas, on ne le considère pas
    # silencieusement comme NEW.
    #
    orphan_raw_keys = (
        set(raw_inventory)
        & manifest_keys
        - set(ingestion_log)
    )

    if orphan_raw_keys:
        details = "\n".join(
            "  - " + " / ".join(str(value) for value in key)
            for key in sorted(orphan_raw_keys)
        )

        raise RuntimeError(
            "\nLots présents dans RAW mais absents de "
            "INGESTION_LOG :\n"
            f"{details}\n"
            "Chargement interrompu pour éviter d'écraser "
            "silencieusement des données existantes."
        )

    #
    # Classification du manifest.
    #
    for item in files:
        key = ingestion_key(item)

        if key not in ingestion_log:
            item["status"] = "NEW"
            pending.append(item)
            continue

        item["status"] = "LOADED"
        item["row_count"] = ingestion_log[key]
        skipped.append(item)

    return pending, skipped

def csv_gz_to_json_gz(source_path, destination_path):
    row_count = 0

    with gzip.open(
        source_path,
        "rt",
        encoding="utf-8",
        newline="",
    ) as source:
        reader = csv.DictReader(source)

        if reader.fieldnames is None:
            raise RuntimeError(
                f"CSV sans en-tête : {source_path}"
            )

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


def load_file(connection, cursor, item):
    country = item["country"]
    location = item["location"]
    snapshot_date = item["snapshot_date"]
    filename = item["filename"]
    target_table = item["target_table"]
    source_path = item["path"]

    target = qualified_table(target_table)
    ingestion_log = qualified_table("INGESTION_LOG")
    stage = stage_path(country, location, snapshot_date)

    print("\n" + "=" * 100)
    print(
        f"{country} / {location} / {snapshot_date} / "
        f"{filename} -> {target_table}"
    )
    print("=" * 100)

    work_dir = PROJECT_ROOT / "target" / "ingestion"
    work_dir.mkdir(parents=True, exist_ok=True)

    json_filename = (
        f"{country}_{location}_{snapshot_date}_"
        f"{filename.replace('.csv.gz', '.json.gz')}"
    )

    json_path = work_dir / json_filename

    try:
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

        print("[3/5] Nettoyage préventif du lot cible")

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
                location,
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
                    %s,
                    %s,
                    TO_DATE(%s),
                    %s,
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

        cursor.execute(
            copy_sql,
            (
                country,
                location,
                snapshot_date,
                filename,
            ),
        )

        loaded_rows = get_raw_row_count(cursor, item)

        print("[5/5] Contrôle et journalisation")
        print(f"      attendu : {expected_rows:,}")
        print(f"      chargé  : {loaded_rows:,}")

        if loaded_rows != expected_rows:
            raise RuntimeError(
                f"Nombre de lignes incohérent pour "
                f"{item['relative_path']}: "
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
                location,
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
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                CURRENT_TIMESTAMP()
            )
            """,
            (
                country,
                location,
                snapshot_date,
                filename,
                target_table,
                loaded_rows,
            ),
        )

        # Un fichier validé devient immédiatement un checkpoint
        # d'ingestion indépendant.
        connection.commit()

        print("      COMMIT OK")

        try:
            print("      Nettoyage du stage...")
            cursor.execute(
                f"REMOVE {stage}/{json_filename}"
            )
            print("      STAGE CLEAN OK")
        except Exception as cleanup_error:
            print(
                "      [WARN] Impossible de nettoyer le stage : "
                f"{cleanup_error}"
            )

    except Exception:
        connection.rollback()
        raise

    finally:
        json_path.unlink(missing_ok=True)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Load verified Inside Airbnb RAW files into Snowflake."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display the ingestion plan without loading data.",
    )

    parser.add_argument(
        "--selection-file",
        help="Geographic selection JSON applied to the local manifest.",
    )

    parser.add_argument(
        "--country",
        help="Only load one country, for example: france",
    )

    parser.add_argument(
        "--location",
        help="Only load one location, for example: lyon",
    )

    parser.add_argument(
        "--snapshot",
        help="Only load one snapshot date, for example: 2026-06-22",
    )

    parser.add_argument(
        "--files",
        nargs="+",
        choices=("listings", "calendar", "reviews"),
        help="Only load selected dataset types.",
    )

    return parser.parse_args()

def filter_files(files, args):
    selected = files

    if args.country:
        country = args.country.strip().lower()
        selected = [
            item
            for item in selected
            if item["country"].lower() == country
        ]

    if args.location:
        location = args.location.strip().lower()
        selected = [
            item
            for item in selected
            if item["location"].lower() == location
        ]

    if args.snapshot:
        selected = [
            item
            for item in selected
            if item["snapshot_date"] == args.snapshot
        ]

    if args.files:
        filenames = {
            f"{dataset}.csv.gz"
            for dataset in args.files
        }

        selected = [
            item
            for item in selected
            if item["filename"] in filenames
        ]

    return selected

def main():
    args = parse_args()
    validate_environment()

    files = load_manifest(args)

    print("=" * 100)
    print("INSIDE AIRBNB -> SNOWFLAKE RAW")
    print("=" * 100)

    print(
        f"Snowflake : "
        f"{SNOWFLAKE_ACCOUNT} / "
        f"{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}"
    )

    print(f"Manifest  : {MANIFEST_PATH}")
    print(f"Fichiers  : {len(files)}")

    if not files:
        raise RuntimeError(
            "Aucun fichier exploitable dans le manifest."
        )

    connection = get_connection()

    try:
        cursor = connection.cursor()

        try:
            ingestion_log = get_ingestion_log(cursor)

            pending, skipped = classify_files(
                cursor,
                files,
                ingestion_log,
            )

            print("\n" + "-" * 100)
            print("PLAN D'INGESTION")
            print("-" * 100)

            print(f"Manifest       : {len(files)}")
            print(f"Déjà chargés   : {len(skipped)}")
            print(f"À charger      : {len(pending)}")

            if skipped:
                print("\nSKIP :")
                for item in skipped:
                    print(
                        f"  [SKIP] "
                        f"{item['relative_path']} "
                        f"({item['row_count']:,} lignes)"
                    )

            if pending:
                print("\nLOAD :")
                for item in pending:
                    print(
                        f"  [LOAD] {item['relative_path']}"
                    )

            if args.dry_run:
                print(
                    "\n[DRY-RUN] Aucun fichier ne sera chargé."
                )
                return

            if not pending:
                print(
                    "\nAucun nouveau fichier à charger."
                )
                return

            for index, item in enumerate(
                pending,
                start=1,
            ):
                print(
                    f"\nFichier {index}/{len(pending)}"
                )

                load_file(
                    connection,
                    cursor,
                    item,
                )

        finally:
            cursor.close()

    finally:
        connection.close()

    print("\n" + "=" * 100)
    print("INGESTION TERMINÉE")
    print(f"Nouveaux fichiers chargés : {len(pending)}")
    print("=" * 100)


if __name__ == "__main__":
    main()