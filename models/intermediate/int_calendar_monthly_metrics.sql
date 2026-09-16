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

monthly as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_id,

        date_trunc('month', calendar_date)::date
            as calendar_month,

        day(last_day(calendar_date))
            as days_in_calendar_month,

        min(calendar_date)
            as first_observed_date,

        max(calendar_date)
            as last_observed_date,

        count(*)
            as represented_day_count,

        count_if(is_available)
            as available_day_count,

        count_if(not is_available)
            as unavailable_day_count

    from calendar

    group by
        source_country,
        source_city,
        snapshot_date,
        listing_id,
        date_trunc('month', calendar_date)::date,
        day(last_day(calendar_date))

),

final as (

    select
        *,

        represented_day_count = days_in_calendar_month
            as has_full_month_coverage,

        round(
            100.0 * represented_day_count
            / nullif(days_in_calendar_month, 0),
            2
        ) as calendar_month_coverage_pct,

        round(
            100.0 * available_day_count
            / nullif(represented_day_count, 0),
            2
        ) as availability_rate_pct,

        round(
            100.0 * unavailable_day_count
            / nullif(represented_day_count, 0),
            2
        ) as unavailability_rate_pct

    from monthly

)

select *
from final