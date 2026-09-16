with neighbourhood as (

    select
        source_country,
        source_city,
        snapshot_date,

        count(*) as neighbourhood_count,
        sum(listing_count) as listing_count,
        sum(listings_with_price) as listings_with_price,
        sum(native_review_count_total) as native_review_count_total,
        sum(reconstructed_review_count_total)
            as reconstructed_review_count_total

    from {{ ref('mart_neighbourhood_snapshot') }}

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
        native_review_count_total,
        reconstructed_review_count_total

    from {{ ref('mart_market_snapshot') }}

)

select
    n.source_country,
    n.source_city,
    n.snapshot_date,

    n.neighbourhood_count,

    n.listing_count as neighbourhood_listing_count,
    m.listing_count as market_listing_count,

    n.listings_with_price as neighbourhood_listings_with_price,
    m.listings_with_price as market_listings_with_price,

    n.native_review_count_total as neighbourhood_native_reviews,
    m.native_review_count_total as market_native_reviews,

    n.reconstructed_review_count_total
        as neighbourhood_reconstructed_reviews,
    m.reconstructed_review_count_total
        as market_reconstructed_reviews

from neighbourhood n

inner join market m
    on n.source_country = m.source_country
   and n.source_city = m.source_city
   and n.snapshot_date = m.snapshot_date

where
       n.listing_count <> m.listing_count

    or n.listings_with_price <> m.listings_with_price

    or n.native_review_count_total
       <> m.native_review_count_total

    or n.reconstructed_review_count_total
       <> m.reconstructed_review_count_total