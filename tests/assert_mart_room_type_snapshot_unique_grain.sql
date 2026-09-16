select
    source_country,
    source_city,
    snapshot_date,
    room_type,
    count(*) as occurrences

from {{ ref('mart_room_type_snapshot') }}

group by
    source_country,
    source_city,
    snapshot_date,
    room_type

having count(*) > 1