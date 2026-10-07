{{
    config(
        materialized='view'
    )
}}

with listing_population as (

    select distinct
        source_country,
        source_city,
        snapshot_date,
        listing_id

    from {{ ref('stg_listings') }}

),

calendar as (

    select
        c.source_country,
        c.source_city,
        c.snapshot_date,
        c.listing_id,
        c.calendar_date,
        c.is_available

    from {{ ref('stg_calendar') }} c

    inner join listing_population l
        on  c.source_country = l.source_country
        and c.source_city = l.source_city
        and c.snapshot_date = l.snapshot_date
        and c.listing_id = l.listing_id

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

        case
            when represented_days_30d = 30 then
                round(
                    100.0 * available_days_30d / 30.0,
                    2
                )
            else null
        end as availability_rate_30d_pct,

        case
            when represented_days_60d = 60 then
                round(
                    100.0 * available_days_60d / 60.0,
                    2
                )
            else null
        end as availability_rate_60d_pct,

        case
            when represented_days_90d = 90 then
                round(
                    100.0 * available_days_90d / 90.0,
                    2
                )
            else null
        end as availability_rate_90d_pct,

        case
            when represented_days_365d = 365 then
                round(
                    100.0 * available_days_365d / 365.0,
                    2
                )
            else null
        end as availability_rate_365d_pct

    from aggregated

)

select *
from final