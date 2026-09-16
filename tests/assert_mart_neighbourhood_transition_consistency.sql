select *

from {{ ref('mart_neighbourhood_transition') }}

where
    previous_listing_count
        <> retained_listing_count
         + disappeared_listing_count
         + moved_out_listing_count

    or current_listing_count
        <> retained_listing_count
         + newly_observed_listing_count
         + returned_after_gap_listing_count
         + moved_in_listing_count

    or net_listing_change
        <> current_listing_count - previous_listing_count

    or abs(
        retention_rate_pct
        + disappearance_rate_pct
        + moved_out_rate_pct
        - 100
    ) > 0.02

    or previous_snapshot_date >= snapshot_date