select *
from {{ ref('mart_calendar_month_snapshot') }}

where
       listing_count <= 0

    or days_in_calendar_month not between 28 and 31

    or min_days_per_listing <= 0

    or max_days_per_listing > days_in_calendar_month

    or min_days_per_listing > max_days_per_listing

    or full_month_listing_count < 0
    or partial_month_listing_count < 0

    or full_month_listing_count
       + partial_month_listing_count
       <> listing_count

    or represented_listing_days <= 0

    or expected_listing_days_for_present_listings
       <> listing_count * days_in_calendar_month

    or represented_listing_days
       > expected_listing_days_for_present_listings

    or available_day_count < 0

    or unavailable_day_count < 0

    or available_day_count
       + unavailable_day_count
       <> represented_listing_days

    or listing_day_coverage_pct not between 0 and 100

    or full_month_listing_share_pct not between 0 and 100

    or market_availability_rate_pct not between 0 and 100

    or market_unavailability_rate_pct not between 0 and 100

    or average_listing_availability_rate_pct not between 0 and 100

    or median_listing_availability_rate_pct not between 0 and 100

    or abs(
        market_availability_rate_pct
        + market_unavailability_rate_pct
        - 100
    ) > 0.01

    or (
        is_full_month_coverage
        and represented_listing_days
            <> expected_listing_days_for_present_listings
    )

    or (
        not is_full_month_coverage
        and represented_listing_days
            = expected_listing_days_for_present_listings
    )

    or (
        is_full_month_coverage
        and full_month_listing_count <> listing_count
    )

    or first_observed_date > last_observed_date

    or first_observed_date < calendar_month

    or last_observed_date > last_day(calendar_month)