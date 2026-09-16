select
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    count(*) as occurrences

from {{ ref('int_listing_snapshot_movement') }}

group by
    source_country,
    source_city,
    snapshot_date,
    listing_id

having count(*) > 1