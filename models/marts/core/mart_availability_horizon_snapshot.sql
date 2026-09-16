{{
    config(
        materialized='table'
    )
}}

with horizon as (

    select *
    from {{ ref('int_listing_availability_horizon') }}

),

aggregated as (

    select
        source_country,
        source_city,
        snapshot_date,

        count(*) as listing_count,

        -- ============================================================
        -- Calendar window
        -- ============================================================
        min(availability_window_start_date)
            as earliest_availability_window_start_date,

        max(availability_window_start_date)
            as latest_availability_window_start_date,

        -- ============================================================
        -- 30 days
        -- ============================================================
        sum(represented_days_30d)
            as represented_days_30d,

        sum(available_days_30d)
            as available_days_30d,

        round(
            100.0 * sum(available_days_30d)
            / nullif(sum(represented_days_30d), 0),
            2
        ) as market_availability_rate_30d_pct,

        round(
            avg(availability_rate_30d_pct),
            2
        ) as average_listing_availability_rate_30d_pct,

        round(
            median(availability_rate_30d_pct),
            2
        ) as median_listing_availability_rate_30d_pct,

        -- ============================================================
        -- 60 days
        -- ============================================================
        sum(represented_days_60d)
            as represented_days_60d,

        sum(available_days_60d)
            as available_days_60d,

        round(
            100.0 * sum(available_days_60d)
            / nullif(sum(represented_days_60d), 0),
            2
        ) as market_availability_rate_60d_pct,

        round(
            avg(availability_rate_60d_pct),
            2
        ) as average_listing_availability_rate_60d_pct,

        round(
            median(availability_rate_60d_pct),
            2
        ) as median_listing_availability_rate_60d_pct,

        -- ============================================================
        -- 90 days
        -- ============================================================
        sum(represented_days_90d)
            as represented_days_90d,

        sum(available_days_90d)
            as available_days_90d,

        round(
            100.0 * sum(available_days_90d)
            / nullif(sum(represented_days_90d), 0),
            2
        ) as market_availability_rate_90d_pct,

        round(
            avg(availability_rate_90d_pct),
            2
        ) as average_listing_availability_rate_90d_pct,

        round(
            median(availability_rate_90d_pct),
            2
        ) as median_listing_availability_rate_90d_pct,

        -- ============================================================
        -- 365 days
        -- ============================================================
        sum(represented_days_365d)
            as represented_days_365d,

        sum(available_days_365d)
            as available_days_365d,

        round(
            100.0 * sum(available_days_365d)
            / nullif(sum(represented_days_365d), 0),
            2
        ) as market_availability_rate_365d_pct,

        round(
            avg(availability_rate_365d_pct),
            2
        ) as average_listing_availability_rate_365d_pct,

        round(
            median(availability_rate_365d_pct),
            2
        ) as median_listing_availability_rate_365d_pct

    from horizon

    group by
        source_country,
        source_city,
        snapshot_date

)

select *
from aggregated