{{
    config(
        materialized='table'
    )
}}

with listing_snapshot as (

    select *
    from {{ ref('fct_listing_snapshot') }}

),

final as (

    select
        source_country,
        source_city,
        snapshot_date,
        neighbourhood,

        -- ============================================================
        -- Supply
        -- ============================================================
        count(*) as listing_count,

        count_if(room_type = 'Entire home/apt')
            as entire_home_listing_count,

        count_if(room_type = 'Private room')
            as private_room_listing_count,

        count_if(room_type = 'Shared room')
            as shared_room_listing_count,

        -- ============================================================
        -- Hosts
        -- ============================================================
        count(distinct host_id)
            as host_count,

        count_if(is_superhost)
            as superhost_listing_count,

        -- ============================================================
        -- Pricing
        -- ============================================================
        count_if(price is not null)
            as listings_with_price,

        round(avg(price), 2)
            as average_price,

        median(price)
            as median_price,

        -- ============================================================
        -- Availability
        --
        -- Public availability must not be interpreted as observed
        -- vacancy or as the inverse of observed occupancy.
        -- ============================================================
        round(avg(availability_rate_pct), 2)
            as average_availability_rate_pct,

        round(avg(availability_30), 2)
            as average_availability_30,

        round(avg(availability_365), 2)
            as average_availability_365,

        -- ============================================================
        -- Reviews - native Inside Airbnb
        -- ============================================================
        sum(number_of_reviews)
            as native_review_count_total,

        -- ============================================================
        -- Reviews - reconstructed from review-level data
        -- ============================================================
        sum(review_count_to_snapshot)
            as reconstructed_review_count_total,

        sum(review_count_l30d)
            as reconstructed_review_count_l30d,

        sum(review_count_l90d)
            as reconstructed_review_count_l90d,

        sum(review_count_l365d)
            as reconstructed_review_count_l365d,

        -- ============================================================
        -- Geography
        -- Representative centre of listing coordinates.
        -- This is NOT an official arrondissement centroid.
        -- ============================================================
        avg(latitude)
            as average_listing_latitude,

        avg(longitude)
            as average_listing_longitude

    from listing_snapshot

    group by
        source_country,
        source_city,
        snapshot_date,
        neighbourhood

)

select *
from final