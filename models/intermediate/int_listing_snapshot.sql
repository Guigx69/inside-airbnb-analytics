with listings as (

    select *
    from {{ ref('stg_listings') }}

),

snapshot_calendar as (

    select
        source_country,
        source_city,
        snapshot_date,

        row_number() over (
            partition by
                source_country,
                source_city
            order by snapshot_date
        ) as snapshot_sequence

    from (
        select distinct
            source_country,
            source_city,
            snapshot_date
        from listings
    )

),

enriched as (

    select
        l.*,

        sc.snapshot_sequence,

        min(l.snapshot_date) over (
            partition by
                l.source_country,
                l.source_city,
                l.listing_id
        ) as first_seen_snapshot,

        max(l.snapshot_date) over (
            partition by
                l.source_country,
                l.source_city,
                l.listing_id
        ) as last_seen_snapshot,

        count(*) over (
            partition by
                l.source_country,
                l.source_city,
                l.listing_id
        ) as snapshot_count,

        lag(l.snapshot_date) over (
            partition by
                l.source_country,
                l.source_city,
                l.listing_id
            order by l.snapshot_date
        ) as previous_snapshot_date,

        lag(sc.snapshot_sequence) over (
            partition by
                l.source_country,
                l.source_city,
                l.listing_id
            order by l.snapshot_date
        ) as previous_snapshot_sequence,

        lag(l.price) over (
            partition by
                l.source_country,
                l.source_city,
                l.listing_id
            order by l.snapshot_date
        ) as previous_price,

        lag(l.host_id) over (
            partition by
                l.source_country,
                l.source_city,
                l.listing_id
            order by l.snapshot_date
        ) as previous_host_id,

        lag(l.room_type) over (
            partition by
                l.source_country,
                l.source_city,
                l.listing_id
            order by l.snapshot_date
        ) as previous_room_type

    from listings l

    inner join snapshot_calendar sc
        on l.source_country = sc.source_country
       and l.source_city = sc.source_city
       and l.snapshot_date = sc.snapshot_date

),


final as (

    select
        *,

        snapshot_date = first_seen_snapshot
            as is_first_observation,

        snapshot_date = last_seen_snapshot
            as is_last_observation,

        case
            when previous_snapshot_date is null then null
            when snapshot_sequence - previous_snapshot_sequence > 1 then true
            else false
        end as has_observation_gap,

        case
            when previous_snapshot_date is null then null
            else snapshot_sequence - previous_snapshot_sequence - 1
        end as missing_snapshot_count,

        case
            when previous_snapshot_date is null then null
            when price is null or previous_price is null then null
            else price - previous_price
        end as price_change,

        case
            when previous_snapshot_date is null then null
            when price is null or previous_price is null then null
            when previous_price = 0 then null
            else round(
                100.0 * (price - previous_price) / previous_price,
                2
            )
        end as price_change_pct,

        case
            when previous_snapshot_date is null then false
            when host_id is distinct from previous_host_id then true
            else false
        end as has_host_changed,

        case
            when previous_snapshot_date is null then false
            when room_type is distinct from previous_room_type then true
            else false
        end as has_room_type_changed,

    from enriched

)

select *
from final