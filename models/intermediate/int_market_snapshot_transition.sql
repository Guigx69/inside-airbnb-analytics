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
        snapshot_sequence,

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
        listing_id

    from {{ ref('int_listing_snapshot') }}

),

movement as (

    select *
    from {{ ref('int_listing_snapshot_movement') }}

),

previous_population as (

    select
        t.source_country,
        t.source_city,
        t.previous_snapshot_date,
        t.snapshot_date,

        count(distinct previous_listing.listing_id)
            as previous_listing_count,

        count(distinct case
            when current_listing.listing_id is not null
            then previous_listing.listing_id
        end) as retained_listing_count,

        count(distinct case
            when current_listing.listing_id is null
            then previous_listing.listing_id
        end) as disappeared_listing_count

    from transitions t

    left join listing_snapshots previous_listing
        on t.source_country = previous_listing.source_country
       and t.source_city = previous_listing.source_city
       and t.previous_snapshot_date = previous_listing.snapshot_date

    left join listing_snapshots current_listing
        on t.source_country = current_listing.source_country
       and t.source_city = current_listing.source_city
       and t.snapshot_date = current_listing.snapshot_date
       and previous_listing.listing_id = current_listing.listing_id

    where t.previous_snapshot_date is not null

    group by
        t.source_country,
        t.source_city,
        t.previous_snapshot_date,
        t.snapshot_date

),

current_population as (

    select
        source_country,
        source_city,
        snapshot_date,

        count(*) as current_listing_count,

        count_if(movement_status = 'retained')
            as retained_listing_count,

        count_if(movement_status = 'newly_observed')
            as newly_observed_listing_count,

        count_if(movement_status = 'returned_after_gap')
            as returned_after_gap_listing_count

    from movement

    where movement_status <> 'baseline'

    group by
        source_country,
        source_city,
        snapshot_date

),

final as (

    select
        p.source_country,
        p.source_city,
        p.previous_snapshot_date,
        p.snapshot_date,

        p.previous_listing_count,
        c.current_listing_count,

        p.retained_listing_count,
        p.disappeared_listing_count,

        c.newly_observed_listing_count,
        c.returned_after_gap_listing_count,

        c.current_listing_count - p.previous_listing_count
            as net_listing_change,

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
       and p.snapshot_date = c.snapshot_date

)

select *
from final