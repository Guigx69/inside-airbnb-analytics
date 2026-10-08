{{ config(materialized='table') }}

with calendar as (

    select *
    from {{ ref('stg_calendar') }}

),

aggregated as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_id,

        count(*) as calendar_row_count,
        count(distinct calendar_date) as calendar_day_count,

        min(calendar_date) as first_calendar_date,
        max(calendar_date) as last_calendar_date,

        count_if(is_available = true) as available_day_count,
        count_if(is_available = false) as unavailable_day_count,

        round(
            100.0 * count_if(is_available = true)
            / nullif(count(*), 0),
            2
        ) as availability_rate_pct,

        round(
            100.0 * count_if(is_available = false)
            / nullif(count(*), 0),
            2
        ) as unavailability_rate_pct,

        min(minimum_nights) as minimum_nights_min,
        max(minimum_nights) as minimum_nights_max,

        min(maximum_nights) as maximum_nights_min,
        max(maximum_nights) as maximum_nights_max

    from calendar

    group by
        source_country,
        source_city,
        snapshot_date,
        listing_id

)

select *
from aggregated