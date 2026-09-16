with mart as (

    select *
    from {{ ref('mart_availability_snapshot') }}

),

source_metrics as (

    select
        source_country,
        source_city,
        snapshot_date,

        count(*) as expected_listing_count,
        sum(calendar_row_count) as expected_calendar_row_count,
        sum(calendar_day_count) as expected_calendar_day_count,
        sum(available_day_count) as expected_available_day_count,
        sum(unavailable_day_count) as expected_unavailable_day_count

    from {{ ref('int_listing_calendar_metrics') }}

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

    -- Source reconciliation
    or m.listing_count <> s.expected_listing_count
    or m.calendar_row_count <> s.expected_calendar_row_count
    or m.calendar_day_count <> s.expected_calendar_day_count
    or m.available_day_count <> s.expected_available_day_count
    or m.unavailable_day_count <> s.expected_unavailable_day_count

    -- Calendar accounting
    or m.calendar_day_count
        <> m.available_day_count + m.unavailable_day_count

    -- Segmentation must reconstruct the population
    or m.listing_count <> (
        m.fully_unavailable_listing_count
        + m.low_availability_listing_count
        + m.medium_low_availability_listing_count
        + m.medium_high_availability_listing_count
        + m.high_availability_listing_count
        + m.fully_available_listing_count
    )

    -- Rates
    or abs(
        (
            m.market_availability_rate_pct
            + m.market_unavailability_rate_pct
        ) - 100
    ) > 0.01

    -- Listing-level percentiles must be ordered
    or not (
        m.p10_listing_availability_rate_pct
            <= m.p25_listing_availability_rate_pct
        and m.p25_listing_availability_rate_pct
            <= m.median_listing_availability_rate_pct
        and m.median_listing_availability_rate_pct
            <= m.p75_listing_availability_rate_pct
        and m.p75_listing_availability_rate_pct
            <= m.p90_listing_availability_rate_pct
    )

    -- Bounds
    or m.market_availability_rate_pct not between 0 and 100
    or m.market_unavailability_rate_pct not between 0 and 100
    or m.average_listing_availability_rate_pct not between 0 and 100
    or m.p10_listing_availability_rate_pct not between 0 and 100
    or m.p25_listing_availability_rate_pct not between 0 and 100
    or m.median_listing_availability_rate_pct not between 0 and 100
    or m.p75_listing_availability_rate_pct not between 0 and 100
    or m.p90_listing_availability_rate_pct not between 0 and 100