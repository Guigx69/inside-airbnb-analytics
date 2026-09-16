{{
    config(
        materialized='view'
    )
}}

with listings as (

    select *
    from {{ ref('int_listing_snapshot') }}

),

host_aggregates as (

    select
        source_country,
        source_city,
        snapshot_date,
        host_id,

        -- ============================================================
        -- Host descriptive attributes
        -- ============================================================
        max(host_name) as host_name,
        min(host_since) as host_since,

        -- ============================================================
        -- Observed portfolio
        -- Counts only listings actually present in this city/snapshot.
        -- ============================================================
        count(*) as observed_listing_count,

        count_if(room_type = 'Entire home/apt')
            as observed_entire_home_listing_count,

        count_if(room_type = 'Private room')
            as observed_private_room_listing_count,

        count_if(room_type = 'Shared room')
            as observed_shared_room_listing_count,

        count_if(price is not null)
            as listings_with_price,

        round(avg(price), 2)
            as average_listing_price,

        median(price)
            as median_listing_price,

        -- ============================================================
        -- Host characteristics
        -- ============================================================
        max(
            case when is_superhost then 1 else 0 end
        ) = 1 as is_superhost,

        max(
            case when is_host_identity_verified then 1 else 0 end
        ) = 1 as is_host_identity_verified,

        -- ============================================================
        -- Inside Airbnb host portfolio attribute
        -- Kept distinct from observed_listing_count.
        -- ============================================================
        max(calculated_host_listings_count)
            as inside_airbnb_calculated_host_listings_count

    from listings

    where host_id is not null

    group by
        source_country,
        source_city,
        snapshot_date,
        host_id

),

final as (

    select
        *,

        -- ============================================================
        -- Observed host segment
        -- ============================================================
        case
            when observed_listing_count = 1
                then '1'
            when observed_listing_count between 2 and 5
                then '2-5'
            when observed_listing_count between 6 and 10
                then '6-10'
            when observed_listing_count between 11 and 20
                then '11-20'
            when observed_listing_count > 20
                then '21+'
        end as observed_host_segment,

        observed_listing_count > 1
            as is_observed_multi_listing_host,

        -- ============================================================
        -- Difference between observed local portfolio and the
        -- Inside Airbnb supplied host portfolio attribute.
        -- ============================================================
        inside_airbnb_calculated_host_listings_count
            - observed_listing_count
            as calculated_vs_observed_listing_difference

    from host_aggregates

)

select *
from final