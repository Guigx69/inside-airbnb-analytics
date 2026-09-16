{{
    config(
        materialized='table'
    )
}}

with listing_snapshots as (

    select *
    from {{ ref('int_listing_snapshot') }}

),

review_metrics as (

    select *
    from {{ ref('int_listing_review_metrics') }}

),

calendar_metrics as (

    select *
    from {{ ref('int_listing_calendar_metrics') }}

),

final as (

    select

        -- ============================================================
        -- Business grain
        -- One row per country / city / snapshot / listing
        -- ============================================================
        l.source_country,
        l.source_city,
        l.snapshot_date,
        l.listing_id,

        -- ============================================================
        -- Listing
        -- ============================================================
        listing_url,
        listing_name,
        listing_source,

        -- ============================================================
        -- Host
        -- ============================================================
        host_id,
        host_name,
        host_since,
        host_location,
        host_response_time,
        host_response_rate,
        host_acceptance_rate,
        is_superhost,
        host_listings_count,
        host_total_listings_count,
        is_host_identity_verified,

        -- ============================================================
        -- Geography
        -- ============================================================
        neighbourhood,
        latitude,
        longitude,

        -- ============================================================
        -- Property
        -- ============================================================
        property_type,
        room_type,
        accommodates,
        bathrooms,
        bathrooms_text,
        bedrooms,
        beds,

        -- ============================================================
        -- Price and stay constraints
        -- ============================================================
        price,
        minimum_nights,
        maximum_nights,

        -- ============================================================
        -- Availability
        -- ============================================================
        has_availability,
        availability_30,
        availability_60,
        availability_90,
        availability_365,

         -- ============================================================
        -- Detailed calendar metrics
        -- Public availability does not imply observed occupancy.
        -- ============================================================
        c.calendar_row_count,
        c.calendar_day_count,
        c.first_calendar_date,
        c.last_calendar_date,
        c.available_day_count,
        c.unavailable_day_count,
        c.availability_rate_pct,
        c.unavailability_rate_pct,
        c.minimum_nights_min as calendar_minimum_nights_min,
        c.minimum_nights_max as calendar_minimum_nights_max,
        c.maximum_nights_min as calendar_maximum_nights_min,
        c.maximum_nights_max as calendar_maximum_nights_max,

        -- ============================================================
        -- Reviews
        -- ============================================================
        number_of_reviews,
        number_of_reviews_ltm,
        number_of_reviews_l30d,
        first_review_date,
        last_review_date,
        review_score_rating,
        reviews_per_month,

        -- ============================================================
        -- Reconstructed review metrics
        -- Derived independently from deduplicated review-level data.
        -- They are intentionally distinct from Inside Airbnb's native
        -- number_of_reviews* attributes.
        -- ============================================================
        rm.review_count_to_snapshot,
        rm.review_count_l30d,
        rm.review_count_l90d,
        rm.review_count_l365d,

        rm.first_review_date_to_snapshot,
        rm.last_review_date_to_snapshot,
        rm.days_since_last_review,

        rm.has_reviews_to_snapshot,
        rm.has_review_l30d,
        rm.has_review_l90d,
        rm.has_review_l365d,

        -- ============================================================
        -- Inside Airbnb estimates
        -- These must not be interpreted as observed occupancy/revenue.
        -- ============================================================
        estimated_occupancy_l365d,
        estimated_revenue_l365d,

        -- ============================================================
        -- Listing characteristics
        -- ============================================================
        license,
        is_instant_bookable,

        calculated_host_listings_count,
        calculated_host_listings_count_entire_homes,
        calculated_host_listings_count_private_rooms,
        calculated_host_listings_count_shared_rooms,

        -- ============================================================
        -- Historical observation metadata
        -- ============================================================
        snapshot_sequence,
        first_seen_snapshot,
        last_seen_snapshot,
        snapshot_count,

        previous_snapshot_date,
        previous_snapshot_sequence,

        is_first_observation,
        is_last_observation,

        has_observation_gap,
        missing_snapshot_count,

        -- ============================================================
        -- Historical changes
        -- ============================================================
        previous_price,
        price_change,
        price_change_pct,

        previous_host_id,
        has_host_changed,

        previous_room_type,
        has_room_type_changed

    from listing_snapshots l

    left join calendar_metrics c
        on l.source_country = c.source_country
       and l.source_city = c.source_city
       and l.snapshot_date = c.snapshot_date
       and l.listing_id = c.listing_id

    left join review_metrics rm
        on  l.source_country = rm.source_country
        and l.source_city = rm.source_city
        and l.snapshot_date = rm.snapshot_date
        and l.listing_id = rm.listing_id
)

select *
from final