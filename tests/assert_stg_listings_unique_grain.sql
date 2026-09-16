select
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    count(*) as row_count

from {{ ref('stg_listings') }}

group by
    source_country,
    source_city,
    snapshot_date,
    listing_id

having count(*) > 1