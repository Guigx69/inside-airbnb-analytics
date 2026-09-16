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

snapshot_transitions as (

    select
        source_country,
        source_city,
        snapshot_date,
        snapshot_sequence,

        lag(snapshot_date) over (
            partition by source_country, source_city
            order by snapshot_sequence
        ) as market_previous_snapshot_date

    from snapshots

),

current_listings as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_id,
        first_seen_snapshot,
        snapshot_count,
        has_observation_gap

    from {{ ref('int_listing_snapshot') }}

),

classified as (

    select
        c.source_country,
        c.source_city,
        c.snapshot_date,
        c.listing_id,

        t.snapshot_sequence,
        t.market_previous_snapshot_date,

        c.first_seen_snapshot,
        c.snapshot_count,
        c.has_observation_gap,

        previous_listing.listing_id is not null
            as was_present_previous_snapshot,

        case
            -- First market snapshot: no transition can be inferred
            when t.market_previous_snapshot_date is null
                then 'baseline'

            -- Present now and also present in immediately preceding snapshot
            when previous_listing.listing_id is not null
                then 'retained'

            -- First time ever observed in our historical window
            when c.first_seen_snapshot = c.snapshot_date
                then 'newly_observed'

            -- Seen historically, absent from previous snapshot, present again
            else 'returned_after_gap'
        end as movement_status

    from current_listings c

    inner join snapshot_transitions t
        on c.source_country = t.source_country
       and c.source_city = t.source_city
       and c.snapshot_date = t.snapshot_date

    left join current_listings previous_listing
        on c.source_country = previous_listing.source_country
       and c.source_city = previous_listing.source_city
       and t.market_previous_snapshot_date = previous_listing.snapshot_date
       and c.listing_id = previous_listing.listing_id

)

select *
from classified