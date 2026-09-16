select
    source_country,
    source_city,
    snapshot_date,
    count(*) as occurrences
from {{ ref('mart_host_snapshot') }}
group by
    source_country,
    source_city,
    snapshot_date
having count(*) > 1