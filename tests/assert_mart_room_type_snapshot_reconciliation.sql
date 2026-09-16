with room_type_agg as (

    select
        source_country,
        source_city,
        snapshot_date,

        sum(listing_count) as listing_count,
        sum(listings_with_price) as listings_with_price,

        sum(reconstructed_review_count_l30d)
            as reconstructed_review_count_l30d,

        sum(reconstructed_review_count_l90d)
            as reconstructed_review_count_l90d,

        sum(reconstructed_review_count_l365d)
            as reconstructed_review_count_l365d,

        sum(listing_share_pct)
            as listing_share_total_pct

    from {{ ref('mart_room_type_snapshot') }}

    group by
        source_country,
        source_city,
        snapshot_date

),

market as (

    select
        source_country,
        source_city,
        snapshot_date,
        listing_count,
        listings_with_price,
        reconstructed_review_count_l30d,
        reconstructed_review_count_l90d,
        reconstructed_review_count_l365d

    from {{ ref('mart_market_snapshot') }}

)

select
    r.source_country,
    r.source_city,
    r.snapshot_date

from room_type_agg r

inner join market m
    on r.source_country = m.source_country
   and r.source_city = m.source_city
   and r.snapshot_date = m.snapshot_date

where
       r.listing_count <> m.listing_count
    or r.listings_with_price <> m.listings_with_price
    or r.reconstructed_review_count_l30d
        <> m.reconstructed_review_count_l30d
    or r.reconstructed_review_count_l90d
        <> m.reconstructed_review_count_l90d
    or r.reconstructed_review_count_l365d
        <> m.reconstructed_review_count_l365d

    -- tolerance for the sum of individually rounded room-type shares
    or r.listing_share_total_pct < 99.99
    or r.listing_share_total_pct > 100.01