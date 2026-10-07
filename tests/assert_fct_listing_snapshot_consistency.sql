with invalid_rows as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_id,

        calendar_row_count,
        calendar_day_count,
        available_day_count,
        unavailable_day_count,
        availability_rate_pct,

        review_count_to_snapshot,
        review_count_l30d,
        review_count_l90d,
        review_count_l365d

    from {{ ref('fct_listing_snapshot') }}

    where
        -- Review metrics are expected for every listing snapshot.
        review_count_to_snapshot is null

        -- When calendar data exists, its metrics must be complete
        -- and internally consistent.
        or (
            calendar_row_count is not null
            and (
                   calendar_day_count is null
                or available_day_count is null
                or unavailable_day_count is null
                or availability_rate_pct is null

                or available_day_count + unavailable_day_count
                    <> calendar_row_count

                or availability_rate_pct not between 0 and 100
            )
        )

        -- Review windows are cumulative.
        or review_count_l30d > review_count_l90d
        or review_count_l90d > review_count_l365d
        or review_count_l365d > review_count_to_snapshot

)

select *
from invalid_rows