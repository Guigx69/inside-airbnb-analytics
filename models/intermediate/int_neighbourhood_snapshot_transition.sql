{{
    config(
        materialized='view'
    )
}}

with snapshots as (

    select distinct
        source_country,
        source_city,
        snapshot_date,
        snapshot_sequence

    from {{ ref('int_listing_snapshot') }}

),

transitions as (

    select
        source_country,
        source_city,
        snapshot_date,

        lag(snapshot_date) over (
            partition by source_country, source_city
            order by snapshot_sequence
        ) as previous_snapshot_date

    from snapshots

),

listing_snapshots as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_id,
        neighbourhood

    from {{ ref('int_listing_snapshot') }}

),

historical_presence as (

    select distinct
        current_row.source_country,
        current_row.source_city,
        current_row.snapshot_date,
        current_row.listing_id

    from listing_snapshots current_row

    inner join listing_snapshots historical_row
        on current_row.source_country = historical_row.source_country
       and current_row.source_city = historical_row.source_city
       and current_row.listing_id = historical_row.listing_id
       and historical_row.snapshot_date < current_row.snapshot_date

),

previous_population as (

    select
        t.source_country,
        t.source_city,
        t.previous_snapshot_date,
        t.snapshot_date,
        p.neighbourhood,

        count(*) as previous_listing_count,

        count_if(
            c.listing_id is not null
            and c.neighbourhood = p.neighbourhood
        ) as retained_listing_count,

        count_if(
            c.listing_id is null
        ) as disappeared_listing_count,

        count_if(
            c.listing_id is not null
            and c.neighbourhood <> p.neighbourhood
        ) as moved_out_listing_count

    from transitions t

    inner join listing_snapshots p
        on t.source_country = p.source_country
       and t.source_city = p.source_city
       and t.previous_snapshot_date = p.snapshot_date

    left join listing_snapshots c
        on t.source_country = c.source_country
       and t.source_city = c.source_city
       and t.snapshot_date = c.snapshot_date
       and p.listing_id = c.listing_id

    where t.previous_snapshot_date is not null

    group by
        t.source_country,
        t.source_city,
        t.previous_snapshot_date,
        t.snapshot_date,
        p.neighbourhood

),

current_population as (

    select
        t.source_country,
        t.source_city,
        t.previous_snapshot_date,
        t.snapshot_date,
        c.neighbourhood,

        count(*) as current_listing_count,

        count_if(
            p.listing_id is not null
            and p.neighbourhood = c.neighbourhood
        ) as retained_listing_count,

        count_if(
            p.listing_id is not null
            and p.neighbourhood <> c.neighbourhood
        ) as moved_in_listing_count,

        count_if(
            p.listing_id is null
            and h.listing_id is null
        ) as newly_observed_listing_count,

        count_if(
            p.listing_id is null
            and h.listing_id is not null
        ) as returned_after_gap_listing_count

    from transitions t

    inner join listing_snapshots c
        on t.source_country = c.source_country
       and t.source_city = c.source_city
       and t.snapshot_date = c.snapshot_date

    left join listing_snapshots p
        on t.source_country = p.source_country
       and t.source_city = p.source_city
       and t.previous_snapshot_date = p.snapshot_date
       and c.listing_id = p.listing_id

    left join historical_presence h
        on c.source_country = h.source_country
       and c.source_city = h.source_city
       and c.snapshot_date = h.snapshot_date
       and c.listing_id = h.listing_id

    where t.previous_snapshot_date is not null

    group by
        t.source_country,
        t.source_city,
        t.previous_snapshot_date,
        t.snapshot_date,
        c.neighbourhood

),

final as (

    select
        p.source_country,
        p.source_city,
        p.previous_snapshot_date,
        p.snapshot_date,
        p.neighbourhood,

        p.previous_listing_count,
        c.current_listing_count,

        p.retained_listing_count,
        p.disappeared_listing_count,
        p.moved_out_listing_count,

        c.newly_observed_listing_count,
        c.returned_after_gap_listing_count,
        c.moved_in_listing_count,

        c.current_listing_count
            - p.previous_listing_count
            as net_listing_change,

        round(
            100.0
            * (c.current_listing_count - p.previous_listing_count)
            / nullif(p.previous_listing_count, 0),
            2
        ) as net_listing_change_pct,

        round(
            100.0 * p.retained_listing_count
            / nullif(p.previous_listing_count, 0),
            2
        ) as retention_rate_pct,

        round(
            100.0 * p.disappeared_listing_count
            / nullif(p.previous_listing_count, 0),
            2
        ) as disappearance_rate_pct

    from previous_population p

    inner join current_population c
        on p.source_country = c.source_country
       and p.source_city = c.source_city
       and p.previous_snapshot_date = c.previous_snapshot_date
       and p.snapshot_date = c.snapshot_date
       and p.neighbourhood = c.neighbourhood

)

select *
from final