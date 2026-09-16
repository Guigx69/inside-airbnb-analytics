select
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    calendar_date,
    count(*) as row_count

from {{ ref('stg_calendar') }}

group by
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    calendar_date

having count(*) > 1