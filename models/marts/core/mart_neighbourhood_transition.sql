{{
    config(
        materialized='table'
    )
}}

with transitions as (

    select *
    from {{ ref('int_neighbourhood_snapshot_transition') }}

),

final as (

    select
        source_country,
        source_city,

        -- ============================================================
        -- Geographic grain
        -- ============================================================
        neighbourhood,

        -- ============================================================
        -- Transition grain
        -- ============================================================
        previous_snapshot_date,
        snapshot_date,

        datediff(
            'day',
            previous_snapshot_date,
            snapshot_date
        ) as days_between_snapshots,

        -- ============================================================
        -- Population
        -- ============================================================
        previous_listing_count,
        current_listing_count,

        net_listing_change,
        net_listing_change_pct,

        -- ============================================================
        -- Stable population
        -- Listing remains in the same neighbourhood.
        -- ============================================================
        retained_listing_count,

        -- ============================================================
        -- Absence from current snapshot
        -- Does NOT prove permanent Airbnb exit.
        -- ============================================================
        disappeared_listing_count,

        -- ============================================================
        -- Geographic movements
        -- Only directly observable between consecutive snapshots.
        -- ============================================================
        moved_out_listing_count,
        moved_in_listing_count,

        -- ============================================================
        -- Current population acquisition / return
        -- ============================================================
        newly_observed_listing_count,
        returned_after_gap_listing_count,

        -- ============================================================
        -- Previous-population rates
        -- ============================================================
        retention_rate_pct,
        disappearance_rate_pct,

        round(
            100.0 * moved_out_listing_count
            / nullif(previous_listing_count, 0),
            2
        ) as moved_out_rate_pct,

        -- ============================================================
        -- Current-population composition
        -- ============================================================
        round(
            100.0 * newly_observed_listing_count
            / nullif(current_listing_count, 0),
            2
        ) as newly_observed_share_pct,

        round(
            100.0 * returned_after_gap_listing_count
            / nullif(current_listing_count, 0),
            2
        ) as returned_after_gap_share_pct,

        round(
            100.0 * moved_in_listing_count
            / nullif(current_listing_count, 0),
            2
        ) as moved_in_share_pct,

        -- ============================================================
        -- Analytical flags
        -- ============================================================
        case
            when returned_after_gap_listing_count > 0
                then true
            else false
        end as has_returned_listings,

        case
            when moved_in_listing_count > 0
              or moved_out_listing_count > 0
                then true
            else false
        end as has_geographic_movement

    from transitions

)

select *
from final