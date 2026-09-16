select
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    review_id,
    count(*) as row_count

from {{ ref('stg_reviews') }}

group by
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    review_id

having count(*) > 1