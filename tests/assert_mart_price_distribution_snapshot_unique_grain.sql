select
    source_country,
    source_city,
    snapshot_date,
    price_band,
    count(*) as occurrences

from {{ ref('mart_price_distribution_snapshot') }}

group by
    source_country,
    source_city,
    snapshot_date,
    price_band

having count(*) > 1