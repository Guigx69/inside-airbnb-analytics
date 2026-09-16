with source as (

    select
        source_country,
        source_city,
        snapshot_date,
        source_file,
        loaded_at,
        raw_data

    from {{ source('inside_airbnb', 'listings') }}

),

renamed_and_typed as (

    select

        -- ---------------------------------------------------------------------
        -- Technical metadata
        -- ---------------------------------------------------------------------

        source_country,
        source_city,
        snapshot_date,
        source_file,
        loaded_at,

        -- ---------------------------------------------------------------------
        -- Listing
        -- ---------------------------------------------------------------------

        try_to_number(raw_data:id::varchar)                         as listing_id,
        raw_data:listing_url::varchar                               as listing_url,
        raw_data:name::varchar                                      as listing_name,
        raw_data:description::varchar                               as listing_description,
        raw_data:source::varchar                                    as listing_source,

        try_to_number(raw_data:scrape_id::varchar)                  as scrape_id,
        try_to_date(raw_data:last_scraped::varchar)                 as last_scraped,

        -- ---------------------------------------------------------------------
        -- Host
        -- ---------------------------------------------------------------------

        try_to_number(raw_data:host_id::varchar)                    as host_id,
        raw_data:host_name::varchar                                 as host_name,
        try_to_date(raw_data:host_since::varchar)                   as host_since,
        raw_data:host_location::varchar                             as host_location,
        raw_data:host_response_time::varchar                        as host_response_time,

        try_to_decimal(
            replace(raw_data:host_response_rate::varchar, '%', ''),
            5,
            2
        ) / 100                                                     as host_response_rate,

        try_to_decimal(
            replace(raw_data:host_acceptance_rate::varchar, '%', ''),
            5,
            2
        ) / 100                                                     as host_acceptance_rate,

        case
            when lower(raw_data:host_is_superhost::varchar) = 't' then true
            when lower(raw_data:host_is_superhost::varchar) = 'f' then false
            else null
        end                                                         as is_superhost,

        try_to_number(raw_data:host_listings_count::varchar)        as host_listings_count,

        try_to_number(
            raw_data:host_total_listings_count::varchar
        )                                                           as host_total_listings_count,

        case
            when lower(raw_data:host_identity_verified::varchar) = 't' then true
            when lower(raw_data:host_identity_verified::varchar) = 'f' then false
            else null
        end                                                         as is_host_identity_verified,

        -- ---------------------------------------------------------------------
        -- Location
        -- ---------------------------------------------------------------------

        raw_data:neighbourhood_cleansed::varchar                    as neighbourhood,
        try_to_double(raw_data:latitude::varchar)                   as latitude,
        try_to_double(raw_data:longitude::varchar)                  as longitude,

        -- ---------------------------------------------------------------------
        -- Property
        -- ---------------------------------------------------------------------

        raw_data:property_type::varchar                             as property_type,
        raw_data:room_type::varchar                                 as room_type,

        try_to_number(raw_data:accommodates::varchar)               as accommodates,
        try_to_decimal(raw_data:bathrooms::varchar, 10, 2)          as bathrooms,
        raw_data:bathrooms_text::varchar                            as bathrooms_text,
        try_to_number(raw_data:bedrooms::varchar)                   as bedrooms,
        try_to_number(raw_data:beds::varchar)                       as beds,

        -- ---------------------------------------------------------------------
        -- Price and stay rules
        -- ---------------------------------------------------------------------

        try_to_decimal(
            replace(
                replace(raw_data:price::varchar, '$', ''),
                ',',
                ''
            ),
            12,
            2
        )                                                           as price,

        try_to_number(raw_data:minimum_nights::varchar)             as minimum_nights,
        try_to_number(raw_data:maximum_nights::varchar)             as maximum_nights,

        -- ---------------------------------------------------------------------
        -- Availability
        -- ---------------------------------------------------------------------

        case
            when lower(raw_data:has_availability::varchar) = 't' then true
            when lower(raw_data:has_availability::varchar) = 'f' then false
            else null
        end                                                         as has_availability,

        try_to_number(raw_data:availability_30::varchar)            as availability_30,
        try_to_number(raw_data:availability_60::varchar)            as availability_60,
        try_to_number(raw_data:availability_90::varchar)            as availability_90,
        try_to_number(raw_data:availability_365::varchar)           as availability_365,

        -- ---------------------------------------------------------------------
        -- Reviews
        -- ---------------------------------------------------------------------

        try_to_number(raw_data:number_of_reviews::varchar)          as number_of_reviews,
        try_to_number(raw_data:number_of_reviews_ltm::varchar)      as number_of_reviews_ltm,
        try_to_number(raw_data:number_of_reviews_l30d::varchar)     as number_of_reviews_l30d,

        try_to_date(raw_data:first_review::varchar)                 as first_review_date,
        try_to_date(raw_data:last_review::varchar)                  as last_review_date,

        try_to_decimal(
            raw_data:review_scores_rating::varchar,
            5,
            2
        )                                                           as review_score_rating,

        try_to_decimal(
            raw_data:reviews_per_month::varchar,
            10,
            2
        )                                                           as reviews_per_month,

        -- ---------------------------------------------------------------------
        -- Inside Airbnb estimates
        -- ---------------------------------------------------------------------

        try_to_decimal(
            raw_data:estimated_occupancy_l365d::varchar,
            10,
            2
        )                                                           as estimated_occupancy_l365d,

        try_to_decimal(
            raw_data:estimated_revenue_l365d::varchar,
            14,
            2
        )                                                           as estimated_revenue_l365d,

        -- ---------------------------------------------------------------------
        -- Booking / licence
        -- ---------------------------------------------------------------------

        raw_data:license::varchar                                   as license,

        case
            when lower(raw_data:instant_bookable::varchar) = 't' then true
            when lower(raw_data:instant_bookable::varchar) = 'f' then false
            else null
        end                                                         as is_instant_bookable,

        -- ---------------------------------------------------------------------
        -- Host portfolio
        -- ---------------------------------------------------------------------

        try_to_number(
            raw_data:calculated_host_listings_count::varchar
        )                                                           as calculated_host_listings_count,

        try_to_number(
            raw_data:calculated_host_listings_count_entire_homes::varchar
        )                                                           as calculated_host_listings_count_entire_homes,

        try_to_number(
            raw_data:calculated_host_listings_count_private_rooms::varchar
        )                                                           as calculated_host_listings_count_private_rooms,

        try_to_number(
            raw_data:calculated_host_listings_count_shared_rooms::varchar
        )                                                           as calculated_host_listings_count_shared_rooms,

        -- ---------------------------------------------------------------------
        -- Fields introduced in later snapshots
        -- Missing JSON keys naturally return NULL in older snapshots.
        -- ---------------------------------------------------------------------

        raw_data:host_profile_id::varchar                           as host_profile_id,

        try_to_number(
            raw_data:hosts_time_as_host_years::varchar
        )                                                           as hosts_time_as_host_years,

        try_to_number(
            raw_data:hosts_time_as_host_months::varchar
        )                                                           as hosts_time_as_host_months,

        try_to_date(
            raw_data:price_quote_checkin_date::varchar
        )                                                           as price_quote_checkin_date,

        try_to_date(
            raw_data:price_quote_checkout_date::varchar
        )                                                           as price_quote_checkout_date,

        try_to_decimal(
            replace(
                replace(
                    raw_data:price_quote_price_per_night::varchar,
                    '$',
                    ''
                ),
                ',',
                ''
            ),
            12,
            2
        )                                                           as price_quote_price_per_night

    from source

)

select *
from renamed_and_typed