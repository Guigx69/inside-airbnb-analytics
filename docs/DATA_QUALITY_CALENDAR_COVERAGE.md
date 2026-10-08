# Data quality — calendar/listing coverage

## Confirmed diagnostic (2026-10-08)

The dbt singular test `tests/assert_stg_calendar_listing_exists.sql` identifies distinct
`(source_country, source_city, snapshot_date, listing_id)` keys present in
`stg_calendar` but absent from `stg_listings` for the same snapshot.

Observed on the existing Snowflake dataset:

- 3,163 distinct unmatched calendar/listing keys.
- 0 of these keys found in `AIRBNB.RAW.RAW_LISTINGS` using the same
  country, city, snapshot date and numeric listing ID.
- 3,163 absent from `RAW_LISTINGS`.
- dbt test severity is `warn`, deliberately retained. Do not suppress the test
  or fabricate matching listing records to obtain a green test suite.

The discrepancy is already present at the RAW listing boundary, rather than
being introduced solely by the `stg_listings` transformation. The precise
upstream cause (source export differences, timing, or incomplete coverage)
has **not** been established.

### Implications

Calendar records without a corresponding listing must not be interpreted as
having listing attributes available. Any downstream inner join between calendar
and listing data excludes these unmatched listing/snapshot keys; measures based
on joined datasets may therefore have a narrower coverage than the raw calendar.
Validate the join logic of each downstream metric before asserting its impact.

### Reproduce the diagnostic (read-only)

```sql
WITH orphan_calendar AS (
    SELECT DISTINCT
        c.source_country, c.source_city, c.snapshot_date, c.listing_id
    FROM AIRBNB.DBT_GGILLET_STAGING.STG_CALENDAR c
    LEFT JOIN AIRBNB.DBT_GGILLET_STAGING.STG_LISTINGS l
      ON c.source_country = l.source_country
     AND c.source_city = l.source_city
     AND c.snapshot_date = l.snapshot_date
     AND c.listing_id = l.listing_id
    WHERE l.listing_id IS NULL
),
raw_listing_keys AS (
    SELECT DISTINCT
        source_country, source_city, snapshot_date,
        TRY_TO_NUMBER(raw_data:id::VARCHAR) AS listing_id
    FROM AIRBNB.RAW.RAW_LISTINGS
)
SELECT COUNT(*) AS total_orphan_listings,
       COUNT_IF(r.listing_id IS NOT NULL) AS found_in_raw,
       COUNT_IF(r.listing_id IS NULL) AS absent_from_raw
FROM orphan_calendar o
LEFT JOIN raw_listing_keys r
  ON o.source_country = r.source_country
 AND o.source_city = r.source_city
 AND o.snapshot_date = r.snapshot_date
 AND o.listing_id = r.listing_id;
```

Adapt database/schema identifiers for other accounts. This query can scan
large RAW datasets and incur Snowflake compute costs.

### Verification status

The user executed `dbt parse`, `dbt compile`, and `dbt test --threads 4`
against an existing Snowflake environment. The test suite reported one
warning on this relationship test; it is not evidence that a new account can
bootstrap the historical RAW data automatically. Fresh-account provisioning,
historical data acquisition and end-to-end rebuild remain to be validated.
