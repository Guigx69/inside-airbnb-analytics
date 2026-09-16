with source as (

    select
        source_country,
        source_city,
        snapshot_date,
        source_file,
        loaded_at,
        raw_data

    from {{ source('inside_airbnb', 'calendar') }}

),

renamed_and_typed as (

    select

        -- Technical metadata
        source_country,
        source_city,
        snapshot_date,
        source_file,
        loaded_at,

        -- Grain
        try_to_number(raw_data:listing_id::varchar) as listing_id,
        try_to_date(raw_data:date::varchar)         as calendar_date,

        -- Availability
        case
            when lower(raw_data:available::varchar) = 't' then true
            when lower(raw_data:available::varchar) = 'f' then false
            else null
        end                                         as is_available,

        -- Pricing
        -- These attributes only exist in some source snapshots.
        try_to_decimal(
            replace(
                replace(raw_data:price::varchar, '$', ''),
                ',',
                ''
            ),
            12,
            2
        )                                           as price,

        try_to_decimal(
            replace(
                replace(raw_data:adjusted_price::varchar, '$', ''),
                ',',
                ''
            ),
            12,
            2
        )                                           as adjusted_price,

        -- Stay constraints
        try_to_number(
            raw_data:minimum_nights::varchar
        )                                           as minimum_nights,

        try_to_number(
            raw_data:maximum_nights::varchar
        )                                           as maximum_nights

    from source

)

select *
from renamed_and_typed