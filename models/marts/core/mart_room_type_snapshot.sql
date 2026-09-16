{{
    config(
        materialized='table'
    )
}}

with listings as (

    select *
    from {{ ref('fct_listing_snapshot') }}

),

aggregated as (

    select
        source_country,
        source_city,
        snapshot_date,
        room_type,

        -- ============================================================
        -- Supply
        -- ============================================================
        count(*) as listing_count,

        count(distinct host_id) as host_count,

        count_if(is_superhost) as superhost_listing_count,

        -- ============================================================
        -- Capacity
        -- ============================================================
        round(avg(accommodates), 2)
            as average_accommodates,

        median(accommodates)
            as median_accommodates,

        round(avg(bedrooms), 2)
            as average_bedrooms,

        median(bedrooms)
            as median_bedrooms,

        round(avg(beds), 2)
            as average_beds,

        median(beds)
            as median_beds,

        -- ============================================================
        -- Price
        -- Null prices are deliberately preserved as missing data.
        -- ============================================================
        count_if(price is not null)
            as listings_with_price,

        round(avg(price), 2)
            as average_price,

        median(price)
            as median_price,

        -- ============================================================
        -- Availability
        -- Availability must not be interpreted as observed occupancy.
        -- ============================================================
        round(avg(availability_rate_pct), 2)
            as average_availability_rate_pct,

        round(avg(availability_30), 2)
            as average_availability_30,

        round(avg(availability_365), 2)
            as average_availability_365,

        -- ============================================================
        -- Reconstructed review activity
        -- ============================================================
        sum(review_count_l30d)
            as reconstructed_review_count_l30d,

        sum(review_count_l90d)
            as reconstructed_review_count_l90d,

        sum(review_count_l365d)
            as reconstructed_review_count_l365d

    from listings

    group by
        source_country,
        source_city,
        snapshot_date,
        room_type

),

final as (

    select
        *,

        round(
            100.0 * listing_count
            / nullif(
                sum(listing_count) over (
                    partition by
                        source_country,
                        source_city,
                        snapshot_date
                ),
                0
            ),
            2
        ) as listing_share_pct,

        round(
            100.0 * superhost_listing_count
            / nullif(listing_count, 0),
            2
        ) as superhost_listing_share_pct

    from aggregated

)

select *
from final