{{
    config(
        materialized='table'
    )
}}

with monthly as (

    select *
    from {{ ref('int_calendar_monthly_metrics') }}

),

aggregated as (

    select
        source_country,
        source_city,
        snapshot_date,
        calendar_month,

        min(days_in_calendar_month)
            as days_in_calendar_month,

        count(*) as listing_count,

        min(first_observed_date)
            as first_observed_date,

        max(last_observed_date)
            as last_observed_date,

        min(represented_day_count)
            as min_days_per_listing,

        max(represented_day_count)
            as max_days_per_listing,

        count_if(has_full_month_coverage)
            as full_month_listing_count,

        count_if(not has_full_month_coverage)
            as partial_month_listing_count,

        sum(represented_day_count)
            as represented_listing_days,

        count(*) * min(days_in_calendar_month)
            as expected_listing_days_for_present_listings,

        sum(available_day_count)
            as available_day_count,

        sum(unavailable_day_count)
            as unavailable_day_count,

        round(
            avg(availability_rate_pct),
            2
        ) as average_listing_availability_rate_pct,

        round(
            median(availability_rate_pct),
            2
        ) as median_listing_availability_rate_pct

    from monthly

    group by
        source_country,
        source_city,
        snapshot_date,
        calendar_month

),

final as (

    select
        *,

        round(
            100.0 * represented_listing_days
            / nullif(expected_listing_days_for_present_listings, 0),
            2
        ) as listing_day_coverage_pct,

        round(
            100.0 * full_month_listing_count
            / nullif(listing_count, 0),
            2
        ) as full_month_listing_share_pct,

        represented_listing_days
            = expected_listing_days_for_present_listings
            as is_full_month_coverage,

        round(
            100.0 * available_day_count
            / nullif(represented_listing_days, 0),
            2
        ) as market_availability_rate_pct,

        round(
            100.0 * unavailable_day_count
            / nullif(represented_listing_days, 0),
            2
        ) as market_unavailability_rate_pct

    from aggregated

)

select *
from final