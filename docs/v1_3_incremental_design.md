# V1.3 — Incremental readiness and partition replacement

Status: **design / preflight only**. No incremental materialization enabled yet.

## Existing measurements (2026-10-08)

- `int_listing_availability_horizon`: table, 6,008,090 rows, 433.24 s.
- `int_listing_calendar_metrics`: table, 6,011,253 rows, 613.58 s.
- Both in parallel: 619.77 s wall clock.
- Targeted tests: 32/32 intermediate and 73/73 downstream marts pass.
- Downstream 3 marts: 136.73 s wall clock.

## Required semantics

Partition key: `(source_country, source_city, snapshot_date)`.
Output grain: partition key + `listing_id`.

- Initial run: build the full history.
- New partition: calculate and insert the entire partition.
- Corrected/reloaded partition: atomically replace the entire output partition (including listing IDs that disappeared).
- A corrected listings partition must also invalidate `int_listing_availability_horizon`, because it joins `stg_calendar` to `stg_listings`.
- A calendar correction invalidates both aggregates.
- Empty or withdrawn partitions require explicit deletion semantics; a merge keyed by listing ID alone cannot remove disappeared IDs.
- Reruns must be idempotent and must not silently drop orphan calendar records (existing quality warning remains).
- The intermediate snapshot-history model uses window functions across snapshots and must be treated separately.

## Preflight: run read-only SQL in Snowflake

```sql
-- 1. RAW metadata availability and column types.
SELECT table_name, column_name, data_type
FROM AIRBNB.INFORMATION_SCHEMA.COLUMNS
WHERE table_schema = 'RAW'
  AND table_name IN ('RAW_CALENDAR', 'RAW_LISTINGS', 'INGESTION_LOG')
ORDER BY table_name, ordinal_position;

-- 2. Check that timestamps are suitable for detecting changed partitions.
SELECT 'CALENDAR' AS source_name,
       COUNT(*) AS rows_total,
       COUNT_IF(loaded_at IS NULL) AS rows_without_loaded_at,
       MIN(loaded_at) AS oldest_loaded_at,
       MAX(loaded_at) AS newest_loaded_at
FROM AIRBNB.RAW.RAW_CALENDAR
UNION ALL
SELECT 'LISTINGS', COUNT(*), COUNT_IF(loaded_at IS NULL),
       MIN(loaded_at), MAX(loaded_at)
FROM AIRBNB.RAW.RAW_LISTINGS;

-- 3. Confirm output uniqueness at the intended grain.
SELECT 'CALENDAR_METRICS' AS model_name,
       COUNT(*) AS rows_total,
       COUNT(DISTINCT source_country || '|' || source_city || '|' ||
              TO_VARCHAR(snapshot_date) || '|' || TO_VARCHAR(listing_id)) AS distinct_grain
FROM AIRBNB.DBT_GGILLET_INTERMEDIATE.INT_LISTING_CALENDAR_METRICS
UNION ALL
SELECT 'AVAILABILITY_HORIZON', COUNT(*),
       COUNT(DISTINCT source_country || '|' || source_city || '|' ||
              TO_VARCHAR(snapshot_date) || '|' || TO_VARCHAR(listing_id))
FROM AIRBNB.DBT_GGILLET_INTERMEDIATE.INT_LISTING_AVAILABILITY_HORIZON;
```

Note: concatenated-grain check is a quick diagnostic, not a replacement for dbt unique-grain tests (NULLs and delimiters can affect the result).

## Implementation gate

Before changing dbt model materialization to `incremental`, inspect the RAW loader's handling of reloads, deduplication and INGESTION_LOG state. Choose an explicit durable change signal or snapshot version. Avoid using `MAX(snapshot_date)` as the only change detector. Confirm transactional partition replacement strategy supported by the Snowflake dbt adapter, including removal of vanished listing IDs and reprocessing of both source dependencies. Add unit/integration regression cases for initial load, unchanged rerun, late snapshot, corrected calendar, corrected listings, and emptied partition.

No dbt build or Snowflake write should be triggered by this document.
