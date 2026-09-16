select
    source_country,
    source_city,
    previous_snapshot_date,
    snapshot_date,
    count(*) as occurrences

from {{ ref('mart_market_transition') }}

group by
    source_country,
    source_city,
    previous_snapshot_date,
    snapshot_date

having count(*) > 1