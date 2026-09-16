{{
    config(
        materialized='table'
    )
}}

with calendar_metrics as (

    select *
    from {{ ref('int_listing_calendar_metrics') }}

),

aggregated as (

    select
        source_country,
        source_city,
        snapshot_date,

        -- ============================================================
        -- Market population
        -- ============================================================
        count(*) as listing_count,

        sum(calendar_row_count)
            as calendar_row_count,

        sum(calendar_day_count)
            as calendar_day_count,

        sum(available_day_count)
            as available_day_count,

        sum(unavailable_day_count)
            as unavailable_day_count,

        -- ============================================================
        -- Market-level availability
        -- Weighted by represented calendar days
        -- ============================================================
        round(
            100.0 * sum(available_day_count)
            / nullif(sum(calendar_day_count), 0),
            2
        ) as market_availability_rate_pct,

        round(
            100.0 * sum(unavailable_day_count)
            / nullif(sum(calendar_day_count), 0),
            2
        ) as market_unavailability_rate_pct,

        -- ============================================================
        -- Listing-level availability distribution
        -- ============================================================
        round(avg(availability_rate_pct), 2)
            as average_listing_availability_rate_pct,

        round(
            percentile_cont(0.10)
                within group (order by availability_rate_pct),
            2
        ) as p10_listing_availability_rate_pct,

        round(
            percentile_cont(0.25)
                within group (order by availability_rate_pct),
            2
        ) as p25_listing_availability_rate_pct,

        round(
            median(availability_rate_pct),
            2
        ) as median_listing_availability_rate_pct,

        round(
            percentile_cont(0.75)
                within group (order by availability_rate_pct),
            2
        ) as p75_listing_availability_rate_pct,

        round(
            percentile_cont(0.90)
                within group (order by availability_rate_pct),
            2
        ) as p90_listing_availability_rate_pct,

        -- ============================================================
        -- Availability segmentation
        --
        -- These are availability bands, NOT occupancy bands.
        -- An unavailable day must not automatically be interpreted
        -- as an observed booked night.
        -- ============================================================
        count_if(available_day_count = 0)
            as fully_unavailable_listing_count,

        count_if(
            availability_rate_pct > 0
            and availability_rate_pct <= 25
        ) as low_availability_listing_count,

        count_if(
            availability_rate_pct > 25
            and availability_rate_pct <= 50
        ) as medium_low_availability_listing_count,

        count_if(
            availability_rate_pct > 50
            and availability_rate_pct <= 75
        ) as medium_high_availability_listing_count,

        count_if(
            availability_rate_pct > 75
            and availability_rate_pct < 100
        ) as high_availability_listing_count,

        count_if(available_day_count = calendar_day_count)
            as fully_available_listing_count

    from calendar_metrics

    group by
        source_country,
        source_city,
        snapshot_date

),

final as (

    select
        *,

        -- ============================================================
        -- Availability segment shares
        -- ============================================================
        round(
            100.0 * fully_unavailable_listing_count
            / nullif(listing_count, 0),
            2
        ) as fully_unavailable_listing_share_pct,

        round(
            100.0 * low_availability_listing_count
            / nullif(listing_count, 0),
            2
        ) as low_availability_listing_share_pct,

        round(
            100.0 * medium_low_availability_listing_count
            / nullif(listing_count, 0),
            2
        ) as medium_low_availability_listing_share_pct,

        round(
            100.0 * medium_high_availability_listing_count
            / nullif(listing_count, 0),
            2
        ) as medium_high_availability_listing_share_pct,

        round(
            100.0 * high_availability_listing_count
            / nullif(listing_count, 0),
            2
        ) as high_availability_listing_share_pct,

        round(
            100.0 * fully_available_listing_count
            / nullif(listing_count, 0),
            2
        ) as fully_available_listing_share_pct

    from aggregated

)

select *
from final