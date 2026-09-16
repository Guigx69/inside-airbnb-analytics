select
    source_country,
    source_city,
    previous_snapshot_date,
    snapshot_date,

    previous_listing_count,
    current_listing_count,

    retained_listing_count,
    disappeared_listing_count,
    newly_observed_listing_count,
    returned_after_gap_listing_count,

    net_listing_change,
    retention_rate_pct,
    disappearance_rate_pct

from {{ ref('int_market_snapshot_transition') }}

where
    -- Previous population reconciliation
    previous_listing_count
        <> retained_listing_count
         + disappeared_listing_count

    -- Current population reconciliation
    or current_listing_count
        <> retained_listing_count
         + newly_observed_listing_count
         + returned_after_gap_listing_count

    -- Net change reconciliation
    or net_listing_change
        <> current_listing_count - previous_listing_count

    -- Counts cannot be negative
    or previous_listing_count < 0
    or current_listing_count < 0
    or retained_listing_count < 0
    or disappeared_listing_count < 0
    or newly_observed_listing_count < 0
    or returned_after_gap_listing_count < 0

    -- Rates must remain valid percentages
    or retention_rate_pct < 0
    or retention_rate_pct > 100

    or disappearance_rate_pct < 0
    or disappearance_rate_pct > 100

    -- Retention + disappearance must represent
    -- the complete previous population
    or abs(
        retention_rate_pct
        + disappearance_rate_pct
        - 100
    ) > 0.01

    -- Chronological consistency
    or previous_snapshot_date >= snapshot_date