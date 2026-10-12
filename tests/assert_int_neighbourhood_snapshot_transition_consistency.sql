select
    source_country,
    source_city,
    previous_snapshot_date,
    snapshot_date,
    neighbourhood,

    previous_listing_count,
    current_listing_count,

    retained_listing_count,
    disappeared_listing_count,
    moved_out_listing_count,

    newly_observed_listing_count,
    returned_after_gap_listing_count,
    moved_in_listing_count,

    net_listing_change,
    net_listing_change_pct,
    retention_rate_pct,
    disappearance_rate_pct

from {{ ref('int_neighbourhood_snapshot_transition') }}

where
    -- Rapprochement de la population précédente
    previous_listing_count
        <> retained_listing_count
         + disappeared_listing_count
         + moved_out_listing_count

    -- Rapprochement de la population actuelle
    or current_listing_count
        <> retained_listing_count
         + newly_observed_listing_count
         + returned_after_gap_listing_count
         + moved_in_listing_count

    -- Net change reconciliation
    or net_listing_change
        <> current_listing_count - previous_listing_count

    -- Counts cannot be negative
    or previous_listing_count < 0
    or current_listing_count < 0
    or retained_listing_count < 0
    or disappeared_listing_count < 0
    or moved_out_listing_count < 0
    or newly_observed_listing_count < 0
    or returned_after_gap_listing_count < 0
    or moved_in_listing_count < 0

    -- Les taux doivent rester des pourcentages valides
    or retention_rate_pct < 0
    or retention_rate_pct > 100

    or disappearance_rate_pct < 0
    or disappearance_rate_pct > 100

    -- Chronological consistency
    or previous_snapshot_date >= snapshot_date