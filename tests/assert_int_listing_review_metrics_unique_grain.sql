select
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    count(*) as occurrences

from {{ ref('int_listing_review_metrics') }}

group by
    source_country,
    source_city,
    snapshot_date,
    listing_id

having count(*) > 1