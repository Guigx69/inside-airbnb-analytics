{{
    config(
        materialized='view'
    )
}}

with calendar as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_id,
        calendar_date,
        is_available

    from {{ ref('stg_calendar') }}

),

anchored as (

    select
        *,

        min(calendar_date) over (
            partition by
                source_country,
                source_city,
                snapshot_date,
                listing_id
        ) as availability_window_start_date

    from calendar

),

classified as (

    select
        *,

        datediff(
            'day',
            availability_window_start_date,
            calendar_date
        ) + 1 as availability_day_number

    from anchored

),

aggregated as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_id,

        min(calendar_date)
            as availability_window_start_date,

        max(calendar_date)
            as availability_window_end_date,

        count(*)
            as calendar_day_count,

        -- ============================================================
        -- 30-day horizon
        -- ============================================================
        count_if(
            availability_day_number <= 30
        ) as represented_days_30d,

        count_if(
            availability_day_number <= 30
            and is_available
        ) as available_days_30d,

        -- ============================================================
        -- 60-day horizon
        -- ============================================================
        count_if(
            availability_day_number <= 60
        ) as represented_days_60d,

        count_if(
            availability_day_number <= 60
            and is_available
        ) as available_days_60d,

        -- ============================================================
        -- 90-day horizon
        -- ============================================================
        count_if(
            availability_day_number <= 90
        ) as represented_days_90d,

        count_if(
            availability_day_number <= 90
            and is_available
        ) as available_days_90d,

        -- ============================================================
        -- Full 365-day horizon
        -- ============================================================
        count_if(
            availability_day_number <= 365
        ) as represented_days_365d,

        count_if(
            availability_day_number <= 365
            and is_available
        ) as available_days_365d

    from classified

    group by
        source_country,
        source_city,
        snapshot_date,
        listing_id

),

final as (

    select
        *,

        round(
            100.0 * available_days_30d
            / nullif(represented_days_30d, 0),
            2
        ) as availability_rate_30d_pct,

        round(
            100.0 * available_days_60d
            / nullif(represented_days_60d, 0),
            2
        ) as availability_rate_60d_pct,

        round(
            100.0 * available_days_90d
            / nullif(represented_days_90d, 0),
            2
        ) as availability_rate_90d_pct,

        round(
            100.0 * available_days_365d
            / nullif(represented_days_365d, 0),
            2
        ) as availability_rate_365d_pct

    from aggregated

)

select *
from final