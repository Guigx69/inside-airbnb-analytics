with source as (

    select
        source_country,
        source_city,
        snapshot_date,
        source_file,
        loaded_at,
        raw_data

    from {{ source('inside_airbnb', 'reviews') }}

),

renamed_and_typed as (

    select

        -- Technical metadata
        source_country,
        source_city,
        snapshot_date,
        source_file,
        loaded_at,

        -- Review
        try_to_number(raw_data:id::varchar)            as review_id,
        try_to_number(raw_data:listing_id::varchar)    as listing_id,
        try_to_date(raw_data:date::varchar)            as review_date,

        -- Reviewer
        try_to_number(raw_data:reviewer_id::varchar)   as reviewer_id,
        raw_data:reviewer_name::varchar                as reviewer_name,

        -- Content
        raw_data:comments::varchar                     as comments

    from source

)

select *
from renamed_and_typed