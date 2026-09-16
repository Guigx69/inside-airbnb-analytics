with invalid_rows as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_id,

        calendar_row_count,
        available_day_count,
        unavailable_day_count,
        availability_rate_pct,

        review_count_to_snapshot,
        review_count_l30d,
        review_count_l90d,
        review_count_l365d

    from {{ ref('fct_listing_snapshot') }}

    where
        -- Calendar metrics must exist
        calendar_row_count is null

        -- Review metrics must exist
        or review_count_to_snapshot is null

        -- Calendar consistency
        or available_day_count + unavailable_day_count
            <> calendar_row_count

        or availability_rate_pct < 0
        or availability_rate_pct > 100

        -- Review-window consistency
        or review_count_l30d > review_count_l90d
        or review_count_l90d > review_count_l365d
        or review_count_l365d > review_count_to_snapshot

)

select *
from invalid_rows