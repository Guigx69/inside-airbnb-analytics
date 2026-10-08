"""Read-only comparison of local CSV.GZ rows and historical Snowflake RAW_DATA.

This proves logical multiset equivalence, NOT the original compressed-file SHA256.
Usage:
  python scripts/audit_legacy_raw.py
  python scripts/audit_legacy_raw.py --output target/legacy_raw_audit.json
"""
import argparse
from collections import Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path

from load_raw_to_snowflake import (
    PROJECT_ROOT,
    FILE_TO_TABLE,
    get_connection,
    qualified_table,
    sha256_file,
)

PILOTS = (
    ("united-states", "pacific-grove", "2026-03-31", "listings.csv.gz"),
    ("united-states", "salem-or", "2026-03-29", "reviews.csv.gz"),
    ("united-states", "pacific-grove", "2026-03-31", "calendar.csv.gz"),
)


def canonical_hash(row):
    """Use identical JSON types/keys for both sides; retain duplicate counts."""
    payload = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def local_counts(path):
    counts = Counter()
    total = 0
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV sans en-tête")
        for row in reader:
            counts[canonical_hash(row)] += 1
            total += 1
    return counts, total


def snowflake_counts(cursor, country, city, snapshot, filename, table):
    # Only SELECT. Snowflake returns VARIANT as a JSON string in the Python connector.
    cursor.execute(
        f"""SELECT RAW_DATA
            FROM {qualified_table(table)}
            WHERE SOURCE_COUNTRY = %s
              AND SOURCE_CITY = %s
              AND SNAPSHOT_DATE = TO_DATE(%s)
              AND SOURCE_FILE = %s""",
        (country, city, snapshot, filename),
    )
    counts = Counter()
    total = 0
    while True:
        rows = cursor.fetchmany(1000)
        if not rows:
            break
        for (raw,) in rows:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(parsed, dict):
                raise ValueError("RAW_DATA n'est pas un objet JSON")
            counts[canonical_hash(parsed)] += 1
            total += 1
    return counts, total


def audit_one(cursor, key, manifest):
    country, city, snapshot, filename = key
    relative = f"data/raw/{country}/{city}/{snapshot}/{filename}"
    result = {
        "path": relative,
        "table": FILE_TO_TABLE[filename],
        "status": "UNVERIFIABLE",
        "local_rows": None,
        "raw_rows": None,
        "missing_rows_in_raw": None,
        "extra_rows_in_raw": None,
        "local_sha256": None,
        "reason": None,
    }
    try:
        if relative not in manifest:
            raise ValueError("Fichier absent du manifeste")
        entry = manifest[relative]
        path = PROJECT_ROOT / Path(relative)
        if not path.is_file():
            raise ValueError("Fichier local absent")
        expected_size = int(entry["size"])
        if path.stat().st_size != expected_size:
            raise ValueError("Taille locale différente du manifeste")
        local_sha = sha256_file(path)
        if local_sha.lower() != entry["sha256"].strip().lower():
            raise ValueError("SHA-256 local différent du manifeste")
        result["local_sha256"] = local_sha
        local, n_local = local_counts(path)
        result["local_rows"] = n_local
        raw, n_raw = snowflake_counts(cursor, country, city, snapshot, filename, result["table"])
        result["raw_rows"] = n_raw
        missing = sum((local - raw).values())
        extra = sum((raw - local).values())
        result["missing_rows_in_raw"] = missing
        result["extra_rows_in_raw"] = extra
        result["status"] = "MATCH" if missing == 0 and extra == 0 else "MISMATCH"
    except Exception as exc:
        result["reason"] = f"{type(exc).__name__}: {exc}"
    return result


def read_manifest():
    path = PROJECT_ROOT / "data_manifest.csv"
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {"path", "size", "sha256"}.issubset(rows[0]):
        raise ValueError("Manifeste vide ou colonnes manquantes")
    entries = {}
    for row in rows:
        key = Path(row["path"]).as_posix()
        if key in entries:
            raise ValueError(f"Doublon dans le manifeste : {key}")
        entries[key] = row
    return entries


def main():
    parser = argparse.ArgumentParser(description="Audit RAW historique en lecture seule")
    parser.add_argument("--output", type=Path, help="Rapport JSON local facultatif")
    args = parser.parse_args()

    manifest = read_manifest()
    results = []
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            for key in PILOTS:
                result = audit_one(cursor, key, manifest)
                results.append(result)
                print(
                    f"{result['status']}: {result['path']} "
                    f"(local={result['local_rows']}, RAW={result['raw_rows']}, "
                    f"manquantes={result['missing_rows_in_raw']}, "
                    f"supplémentaires={result['extra_rows_in_raw']})"
                )
                if result["reason"]:
                    print(f"  Raison : {result['reason']}")
        finally:
            cursor.close()
    finally:
        connection.close()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {"method": "canonical_json_multiset_sha256_v1",
                 "disclaimer": "Logical equivalence only; not original compressed-file identity",
                 "results": results},
                indent=2, ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"Rapport : {args.output}")

    return 0 if all(r["status"] == "MATCH" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
