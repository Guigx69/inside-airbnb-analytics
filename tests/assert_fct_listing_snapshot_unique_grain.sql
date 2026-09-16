select
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    count(*) as occurrences

from {{ ref('fct_listing_snapshot') }}

group by
    source_country,
    source_city,
    snapshot_date,
    listing_id

having count(*) > 1