select
    source_country,
    source_city,
    snapshot_date,
    host_id,
    count(*) as occurrences

from {{ ref('int_host_snapshot') }}

group by
    source_country,
    source_city,
    snapshot_date,
    host_id

having count(*) > 1