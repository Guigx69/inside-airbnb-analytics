"""Read-only reload planner for Inside Airbnb RAW.

Classifies manifest entries against INGESTION_LOG and RAW row-count inventory.
Never executes DELETE, COPY, INSERT or COMMIT.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from load_raw_to_snowflake import (
    load_manifest, get_connection, get_ingestion_log, get_raw_inventory,
    ingestion_key,
)


def classify(item, log, inventory):
    key = ingestion_key(item)
    record = log.get(key)
    raw_count = inventory.get(key)
    if record is None:
        if raw_count is not None:
            return "BLOCKED_RAW_ORPHAN", "RAW exists without journal"
        return "NEW", "No journal or RAW rows"
    expected = record["row_count"]
    if raw_count is None and expected == 0:
        raw_count = 0
    if raw_count != expected:
        return "BLOCKED_COUNT_MISMATCH", f"journal={expected}, raw={raw_count}"
    old_hash = record["sha256"]
    if not old_hash:
        return "LEGACY_UNCERTIFIED", "Historical compressed-file SHA-256 unavailable"
    if old_hash.lower() == item["sha256"].lower():
        return "UNCHANGED", "Recorded SHA-256 matches local manifest"
    return "RELOAD_CANDIDATE", "Recorded SHA-256 differs from verified local manifest"


def main():
    parser = argparse.ArgumentParser(description="Read-only RAW reload impact plan")
    parser.add_argument("--selection-file", help="Optional geography selection JSON")
    parser.add_argument("--country")
    parser.add_argument("--location")
    parser.add_argument("--snapshot")
    parser.add_argument("--files", nargs="+", choices=("listings", "calendar", "reviews"))
    parser.add_argument("--output", type=Path, default=Path("target/reload_plan.json"))
    args = parser.parse_args()
    # load_manifest verifies local bytes against manifest before any Snowflake access.
    files = load_manifest(args)
    if not files:
        parser.error("No matching manifest entries")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        try:
            log = get_ingestion_log(cursor)
            inventory = get_raw_inventory(cursor)
        finally:
            cursor.close()
    finally:
        connection.close()

    rows = []
    for item in files:
        status, reason = classify(item, log, inventory)
        impacts = []
        if status in ("RELOAD_CANDIDATE", "LEGACY_UNCERTIFIED"):
            if item["filename"] == "calendar.csv.gz":
                impacts = ["int_listing_calendar_metrics", "int_listing_availability_horizon",
                           "fct_listing_snapshot", "mart_availability_snapshot",
                           "mart_availability_horizon_snapshot"]
            elif item["filename"] == "listings.csv.gz":
                impacts = ["int_listing_availability_horizon", "int_listing_snapshot",
                           "fct_listing_snapshot", "mart_availability_snapshot",
                           "mart_availability_horizon_snapshot"]
            else:
                impacts = ["review-dependent models (dependency analysis required)"]
        rows.append({
            "path": item["relative_path"], "status": status, "reason": reason,
            "partition": {"source_country": item["country"],
                          "source_city": item["location"],
                          "snapshot_date": item["snapshot_date"]},
            "dataset": item["filename"], "dbt_impact_candidates": impacts,
        })
    counts = {status: sum(r["status"] == status for r in rows)
              for status in ("UNCHANGED", "NEW", "RELOAD_CANDIDATE",
                             "LEGACY_UNCERTIFIED", "BLOCKED_RAW_ORPHAN",
                             "BLOCKED_COUNT_MISMATCH")}
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "read_only": True,
              "warning": "Impact candidates are not an exhaustive dbt dependency graph",
              "summary": counts, "files": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print("PLAN READ-ONLY:", counts)
    print(f"Report: {args.output}")
    return 1 if any(r["status"].startswith("BLOCKED") for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
