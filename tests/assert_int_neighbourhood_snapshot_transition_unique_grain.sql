select
    source_country,
    source_city,
    previous_snapshot_date,
    snapshot_date,
    neighbourhood,
    count(*) as occurrences

from {{ ref('int_neighbourhood_snapshot_transition') }}

group by
    source_country,
    source_city,
    previous_snapshot_date,
    snapshot_date,
    neighbourhood

having count(*) > 1