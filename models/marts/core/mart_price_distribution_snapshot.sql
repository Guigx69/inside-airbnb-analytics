{{
    config(
        materialized='table'
    )
}}

with listings as (

    select *
    from {{ ref('fct_listing_snapshot') }}

),

classified as (

    select
        *,

        case
            when price is null then 'NO_PRICE'
            when price < 50 then '01_<50'
            when price < 100 then '02_50_99'
            when price < 150 then '03_100_149'
            when price < 200 then '04_150_199'
            when price < 300 then '05_200_299'
            else '06_300_PLUS'
        end as price_band,

        case
            when price is null then 0
            when price < 50 then 1
            when price < 100 then 2
            when price < 150 then 3
            when price < 200 then 4
            when price < 300 then 5
            else 6
        end as price_band_order

    from listings

),

aggregated as (

    select
        source_country,
        source_city,
        snapshot_date,
        price_band,
        price_band_order,

        count(*) as listing_count,

        count_if(price is not null)
            as listings_with_price,

        round(avg(price), 2)
            as average_price,

        median(price)
            as median_price,

        min(price)
            as min_price,

        max(price)
            as max_price,

        round(avg(availability_rate_pct), 2)
            as average_availability_rate_pct,

        sum(review_count_l30d)
            as reconstructed_review_count_l30d,

        sum(review_count_l90d)
            as reconstructed_review_count_l90d,

        sum(review_count_l365d)
            as reconstructed_review_count_l365d

    from classified

    group by
        source_country,
        source_city,
        snapshot_date,
        price_band,
        price_band_order

),

final as (

    select
        *,

        round(
            100.0 * listing_count
            / nullif(
                sum(listing_count) over (
                    partition by
                        source_country,
                        source_city,
                        snapshot_date
                ),
                0
            ),
            2
        ) as market_listing_share_pct,

        round(
            100.0 * listings_with_price
            / nullif(
                sum(listings_with_price) over (
                    partition by
                        source_country,
                        source_city,
                        snapshot_date
                ),
                0
            ),
            2
        ) as priced_listing_share_pct

    from aggregated

)

select *
from final