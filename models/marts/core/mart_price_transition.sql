{{
    config(
        materialized='table'
    )
}}

with listings as (

    select *
    from {{ ref('int_listing_snapshot') }}

    where previous_snapshot_date is not null

),

aggregated as (

    select
        source_country,
        source_city,
        previous_snapshot_date,
        snapshot_date,

        datediff(
            day,
            previous_snapshot_date,
            snapshot_date
        ) as days_between_observations,

        case
            when missing_snapshot_count = 0
                then 'CONSECUTIVE'
            else 'AFTER_GAP'
        end as transition_type,

        missing_snapshot_count,

        count(*) as listing_observation_count,

        count_if(previous_price is not null)
            as listings_with_previous_price,

        count_if(price is not null)
            as listings_with_current_price,

        count_if(
            previous_price is not null
            and price is not null
        ) as comparable_listing_count,

        count_if(
            previous_price is not null
            and price is not null
            and price > previous_price
        ) as price_increase_count,

        count_if(
            previous_price is not null
            and price is not null
            and price < previous_price
        ) as price_decrease_count,

        count_if(
            previous_price is not null
            and price is not null
            and price = previous_price
        ) as unchanged_price_count,

        avg(
            case
                when previous_price is not null
                 and price is not null
                    then previous_price
            end
        ) as average_previous_price,

        avg(
            case
                when previous_price is not null
                 and price is not null
                    then price
            end
        ) as average_current_price,

        median(
            case
                when previous_price is not null
                 and price is not null
                    then previous_price
            end
        ) as median_previous_price,

        median(
            case
                when previous_price is not null
                 and price is not null
                    then price
            end
        ) as median_current_price,

        avg(
            case
                when previous_price is not null
                 and price is not null
                    then price_change
            end
        ) as average_price_change,

        median(
            case
                when previous_price is not null
                 and price is not null
                    then price_change
            end
        ) as median_price_change,

        avg(
            case
                when previous_price is not null
                 and price is not null
                    then price_change_pct
            end
        ) as average_price_change_pct,

        median(
            case
                when previous_price is not null
                 and price is not null
                    then price_change_pct
            end
        ) as median_price_change_pct

    from listings

    group by
        source_country,
        source_city,
        previous_snapshot_date,
        snapshot_date,
        missing_snapshot_count

),

final as (

    select
        *,

        round(
            100.0 * comparable_listing_count
            / nullif(listing_observation_count, 0),
            2
        ) as comparable_price_coverage_pct,

        round(
            100.0 * price_increase_count
            / nullif(comparable_listing_count, 0),
            2
        ) as price_increase_share_pct,

        round(
            100.0 * price_decrease_count
            / nullif(comparable_listing_count, 0),
            2
        ) as price_decrease_share_pct,

        round(
            100.0 * unchanged_price_count
            / nullif(comparable_listing_count, 0),
            2
        ) as unchanged_price_share_pct

    from aggregated

)

select *
from final