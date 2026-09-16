select
    source_country,
    source_city,
    listing_id,
    review_id,
    count(*) as row_count

from {{ ref('int_reviews') }}

group by
    source_country,
    source_city,
    listing_id,
    review_id

having count(*) > 1