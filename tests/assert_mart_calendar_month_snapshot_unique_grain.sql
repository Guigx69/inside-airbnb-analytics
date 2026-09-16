select
    source_country,
    source_city,
    snapshot_date,
    calendar_month,
    count(*) as occurrences

from {{ ref('mart_calendar_month_snapshot') }}

group by
    source_country,
    source_city,
    snapshot_date,
    calendar_month

having count(*) > 1