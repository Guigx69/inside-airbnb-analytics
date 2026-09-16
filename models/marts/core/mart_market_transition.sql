{{
    config(
        materialized='table'
    )
}}

with transitions as (

    select *
    from {{ ref('int_market_snapshot_transition') }}

),

final as (

    select
        source_country,
        source_city,

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
        -- Market population
        -- ============================================================
        previous_listing_count,
        current_listing_count,

        current_listing_count - previous_listing_count
            as net_listing_change,

        round(
            100.0
            * (current_listing_count - previous_listing_count)
            / nullif(previous_listing_count, 0),
            2
        ) as net_listing_change_pct,

        -- ============================================================
        -- Movement between consecutive snapshots
        -- ============================================================
        retained_listing_count,
        disappeared_listing_count,
        newly_observed_listing_count,
        returned_after_gap_listing_count,

        -- ============================================================
        -- Movement rates
        -- ============================================================
        retention_rate_pct,
        disappearance_rate_pct,

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

        -- ============================================================
        -- Analytical warning
        --
        -- "Disappeared" means absent from the next snapshot.
        -- It must not be interpreted as a confirmed Airbnb exit.
        -- ============================================================
        case
            when returned_after_gap_listing_count > 0
                then true
            else false
        end as has_returned_listings

    from transitions

)

select *
from final