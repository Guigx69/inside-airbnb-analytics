{{ config(severity='warn') }}

select distinct
    calendar.source_country,
    calendar.source_city,
    calendar.snapshot_date,
    calendar.listing_id

from {{ ref('stg_calendar') }} as calendar

left join {{ ref('stg_listings') }} as listings
    on calendar.source_country = listings.source_country
    and calendar.source_city = listings.source_city
    and calendar.snapshot_date = listings.snapshot_date
    and calendar.listing_id = listings.listing_id

where listings.listing_id is null