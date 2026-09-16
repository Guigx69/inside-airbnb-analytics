select
    source_country,
    source_city,
    snapshot_date,
    calendar_month,
    listing_id,
    count(*) as occurrences

from {{ ref('int_calendar_monthly_metrics') }}

group by
    source_country,
    source_city,
    snapshot_date,
    calendar_month,
    listing_id

having count(*) > 1