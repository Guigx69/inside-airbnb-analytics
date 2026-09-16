select
    *

from {{ ref('int_listing_availability_horizon') }}

where
       calendar_day_count <> 365

    -- Every horizon must be completely represented
    or represented_days_30d <> 30
    or represented_days_60d <> 60
    or represented_days_90d <> 90
    or represented_days_365d <> 365

    -- Available days cannot exceed their horizon
    or available_days_30d not between 0 and 30
    or available_days_60d not between 0 and 60
    or available_days_90d not between 0 and 90
    or available_days_365d not between 0 and 365

    -- Cumulative availability must be monotonic
    or available_days_30d > available_days_60d
    or available_days_60d > available_days_90d
    or available_days_90d > available_days_365d

    -- Rates must remain valid percentages
    or availability_rate_30d_pct not between 0 and 100
    or availability_rate_60d_pct not between 0 and 100
    or availability_rate_90d_pct not between 0 and 100
    or availability_rate_365d_pct not between 0 and 100

    -- Calendar window must contain exactly 365 consecutive dates
    or datediff(
        'day',
        availability_window_start_date,
        availability_window_end_date
    ) <> 364