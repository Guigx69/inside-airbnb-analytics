select *
from {{ ref('int_calendar_monthly_metrics') }}

where
       represented_day_count <= 0

    or represented_day_count > days_in_calendar_month

    or available_day_count < 0

    or unavailable_day_count < 0

    or available_day_count + unavailable_day_count
        <> represented_day_count

    or calendar_month_coverage_pct < 0
    or calendar_month_coverage_pct > 100

    or availability_rate_pct < 0
    or availability_rate_pct > 100

    or unavailability_rate_pct < 0
    or unavailability_rate_pct > 100

    or abs(
        availability_rate_pct
        + unavailability_rate_pct
        - 100
    ) > 0.01

    or (
        has_full_month_coverage
        and represented_day_count <> days_in_calendar_month
    )

    or (
        not has_full_month_coverage
        and represented_day_count = days_in_calendar_month
    )

    or first_observed_date > last_observed_date

    or first_observed_date < calendar_month

    or last_observed_date > last_day(calendar_month)

    or first_observed_date > last_day(calendar_month)

    or date_trunc('month', first_observed_date)::date
        <> calendar_month

    or date_trunc('month', last_observed_date)::date
        <> calendar_month