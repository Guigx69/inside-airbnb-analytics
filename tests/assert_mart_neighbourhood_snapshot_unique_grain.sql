select
    source_country,
    source_city,
    snapshot_date,
    neighbourhood,
    count(*) as occurrences

from {{ ref('mart_neighbourhood_snapshot') }}

group by
    source_country,
    source_city,
    snapshot_date,
    neighbourhood

having count(*) > 1