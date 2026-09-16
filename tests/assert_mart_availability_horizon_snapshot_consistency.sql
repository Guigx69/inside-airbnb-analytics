with mart as (

    select *
    from {{ ref('mart_availability_horizon_snapshot') }}

),

source_metrics as (

    select
        source_country,
        source_city,
        snapshot_date,

        count(*) as expected_listing_count,

        min(availability_window_start_date)
            as expected_earliest_window_start_date,

        max(availability_window_start_date)
            as expected_latest_window_start_date,

        sum(represented_days_30d)
            as expected_represented_days_30d,

        sum(available_days_30d)
            as expected_available_days_30d,

        sum(represented_days_60d)
            as expected_represented_days_60d,

        sum(available_days_60d)
            as expected_available_days_60d,

        sum(represented_days_90d)
            as expected_represented_days_90d,

        sum(available_days_90d)
            as expected_available_days_90d,

        sum(represented_days_365d)
            as expected_represented_days_365d,

        sum(available_days_365d)
            as expected_available_days_365d

    from {{ ref('int_listing_availability_horizon') }}

    group by
        source_country,
        source_city,
        snapshot_date

)

select
    m.*

from mart m

left join source_metrics s
    on m.source_country = s.source_country
   and m.source_city = s.source_city
   and m.snapshot_date = s.snapshot_date

where
       s.snapshot_date is null

    -- Population
    or m.listing_count <> s.expected_listing_count

    -- Window boundaries
    or m.earliest_availability_window_start_date
        <> s.expected_earliest_window_start_date

    or m.latest_availability_window_start_date
        <> s.expected_latest_window_start_date

    -- Source reconciliation
    or m.represented_days_30d
        <> s.expected_represented_days_30d

    or m.available_days_30d
        <> s.expected_available_days_30d

    or m.represented_days_60d
        <> s.expected_represented_days_60d

    or m.available_days_60d
        <> s.expected_available_days_60d

    or m.represented_days_90d
        <> s.expected_represented_days_90d

    or m.available_days_90d
        <> s.expected_available_days_90d

    or m.represented_days_365d
        <> s.expected_represented_days_365d

    or m.available_days_365d
        <> s.expected_available_days_365d

    -- Complete horizon representation
    or m.represented_days_30d <> m.listing_count * 30
    or m.represented_days_60d <> m.listing_count * 60
    or m.represented_days_90d <> m.listing_count * 90
    or m.represented_days_365d <> m.listing_count * 365

    -- Available days cannot exceed represented days
    or m.available_days_30d not between 0 and m.represented_days_30d
    or m.available_days_60d not between 0 and m.represented_days_60d
    or m.available_days_90d not between 0 and m.represented_days_90d
    or m.available_days_365d not between 0 and m.represented_days_365d

    -- Percentage bounds
    or m.market_availability_rate_30d_pct not between 0 and 100
    or m.market_availability_rate_60d_pct not between 0 and 100
    or m.market_availability_rate_90d_pct not between 0 and 100
    or m.market_availability_rate_365d_pct not between 0 and 100

    or m.average_listing_availability_rate_30d_pct not between 0 and 100
    or m.average_listing_availability_rate_60d_pct not between 0 and 100
    or m.average_listing_availability_rate_90d_pct not between 0 and 100
    or m.average_listing_availability_rate_365d_pct not between 0 and 100

    or m.median_listing_availability_rate_30d_pct not between 0 and 100
    or m.median_listing_availability_rate_60d_pct not between 0 and 100
    or m.median_listing_availability_rate_90d_pct not between 0 and 100
    or m.median_listing_availability_rate_365d_pct not between 0 and 100

    -- With complete equal-sized horizons, the weighted market rate
    -- and the average listing rate must reconcile after rounding
    or abs(
        m.market_availability_rate_30d_pct
        - m.average_listing_availability_rate_30d_pct
    ) > 0.01

    or abs(
        m.market_availability_rate_60d_pct
        - m.average_listing_availability_rate_60d_pct
    ) > 0.01

    or abs(
        m.market_availability_rate_90d_pct
        - m.average_listing_availability_rate_90d_pct
    ) > 0.01

    or abs(
        m.market_availability_rate_365d_pct
        - m.average_listing_availability_rate_365d_pct
    ) > 0.01