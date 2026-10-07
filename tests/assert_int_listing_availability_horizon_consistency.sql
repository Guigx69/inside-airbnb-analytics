select
    *

from {{ ref('int_listing_availability_horizon') }}

where
       -- Represented days must remain within each analytical horizon
       represented_days_30d not between 1 and 30
    or represented_days_60d not between 1 and 60
    or represented_days_90d not between 1 and 90
    or represented_days_365d not between 1 and 365

    -- Represented horizons must be cumulative
    or represented_days_30d > represented_days_60d
    or represented_days_60d > represented_days_90d
    or represented_days_90d > represented_days_365d

    -- Availability rates are valid only with complete horizon coverage
    or (
        represented_days_30d = 30
        and availability_rate_30d_pct is null
    )
    or (
        represented_days_30d <> 30
        and availability_rate_30d_pct is not null
    )

    or (
        represented_days_60d = 60
        and availability_rate_60d_pct is null
    )
    or (
        represented_days_60d <> 60
        and availability_rate_60d_pct is not null
    )

    or (
        represented_days_90d = 90
        and availability_rate_90d_pct is null
    )
    or (
        represented_days_90d <> 90
        and availability_rate_90d_pct is not null
    )

    or (
        represented_days_365d = 365
        and availability_rate_365d_pct is null
    )
    or (
        represented_days_365d <> 365
        and availability_rate_365d_pct is not null
    )

    -- Available days cannot exceed represented days
    or available_days_30d not between 0 and represented_days_30d
    or available_days_60d not between 0 and represented_days_60d
    or available_days_90d not between 0 and represented_days_90d
    or available_days_365d not between 0 and represented_days_365d

    -- Cumulative availability must be monotonic
    or available_days_30d > available_days_60d
    or available_days_60d > available_days_90d
    or available_days_90d > available_days_365d

    -- Non-null rates must remain valid percentages
    or (
        availability_rate_30d_pct is not null
        and availability_rate_30d_pct not between 0 and 100
    )
    or (
        availability_rate_60d_pct is not null
        and availability_rate_60d_pct not between 0 and 100
    )
    or (
        availability_rate_90d_pct is not null
        and availability_rate_90d_pct not between 0 and 100
    )
    or (
        availability_rate_365d_pct is not null
        and availability_rate_365d_pct not between 0 and 100
    )