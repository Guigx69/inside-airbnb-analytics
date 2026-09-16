{{
    config(
        materialized='table'
    )
}}

with hosts as (

    select *
    from {{ ref('int_host_snapshot') }}

),

ranked_hosts as (

    select
        *,

        count(*) over (
            partition by
                source_country,
                source_city,
                snapshot_date
        ) as market_host_count,

        sum(observed_listing_count) over (
            partition by
                source_country,
                source_city,
                snapshot_date
        ) as market_listing_count,

        row_number() over (
            partition by
                source_country,
                source_city,
                snapshot_date
            order by
                observed_listing_count desc,
                host_id
        ) as host_rank

    from hosts

),

aggregated as (

    select
        source_country,
        source_city,
        snapshot_date,

        -- ============================================================
        -- Market population
        -- ============================================================
        count(*) as host_count,
        sum(observed_listing_count) as listing_count,

        round(
            1.0 * sum(observed_listing_count)
            / nullif(count(*), 0),
            2
        ) as average_listings_per_host,

        median(observed_listing_count)
            as median_listings_per_host,

        max(observed_listing_count)
            as max_listings_per_host,

        -- ============================================================
        -- Host segmentation
        -- ============================================================
        count_if(observed_host_segment = '1')
            as single_listing_host_count,

        count_if(observed_host_segment = '2-5')
            as host_count_2_to_5,

        count_if(observed_host_segment = '6-10')
            as host_count_6_to_10,

        count_if(observed_host_segment = '11-20')
            as host_count_11_to_20,

        count_if(observed_host_segment = '21+')
            as host_count_21_plus,

        count_if(is_observed_multi_listing_host)
            as multi_listing_host_count,

        -- ============================================================
        -- Listings controlled by host type
        -- ============================================================
        sum(
            case
                when observed_listing_count = 1
                    then observed_listing_count
                else 0
            end
        ) as listings_controlled_by_single_listing_hosts,

        sum(
            case
                when observed_listing_count > 1
                    then observed_listing_count
                else 0
            end
        ) as listings_controlled_by_multi_listing_hosts,

        -- ============================================================
        -- Host characteristics
        -- ============================================================
        count_if(is_superhost)
            as superhost_count,

        count_if(is_host_identity_verified)
            as identity_verified_host_count,

        -- ============================================================
        -- Price coverage
        -- ============================================================
        sum(listings_with_price)
            as listings_with_price,

         -- ============================================================
        -- Host concentration
        -- Top X% thresholds use CEIL so that small populations still
        -- contain at least the requested proportion of hosts.
        -- ============================================================
        sum(
            case
                when host_rank <= ceil(market_host_count * 0.01)
                    then observed_listing_count
                else 0
            end
        ) as listings_controlled_by_top_1_pct_hosts,

        sum(
            case
                when host_rank <= ceil(market_host_count * 0.05)
                    then observed_listing_count
                else 0
            end
        ) as listings_controlled_by_top_5_pct_hosts,

        sum(
            case
                when host_rank <= ceil(market_host_count * 0.10)
                    then observed_listing_count
                else 0
            end
        ) as listings_controlled_by_top_10_pct_hosts,

        round(
            sum(
                power(
                    100.0 * observed_listing_count
                    / nullif(market_listing_count, 0),
                    2
                )
            ),
            2
        ) as host_hhi

    from ranked_hosts

    group by
        source_country,
        source_city,
        snapshot_date

),

final as (

    select
        *,

        -- ============================================================
        -- Host shares
        -- ============================================================
        round(
            100.0 * single_listing_host_count
            / nullif(host_count, 0),
            2
        ) as single_listing_host_share_pct,

        round(
            100.0 * multi_listing_host_count
            / nullif(host_count, 0),
            2
        ) as multi_listing_host_share_pct,

        -- ============================================================
        -- Concentration indicators
        -- ============================================================
        round(
            100.0 * listings_controlled_by_top_1_pct_hosts
            / nullif(listing_count, 0),
            2
        ) as top_1_pct_listing_share_pct,

        round(
            100.0 * listings_controlled_by_top_5_pct_hosts
            / nullif(listing_count, 0),
            2
        ) as top_5_pct_listing_share_pct,

        round(
            100.0 * listings_controlled_by_top_10_pct_hosts
            / nullif(listing_count, 0),
            2
        ) as top_10_pct_listing_share_pct,

        -- ============================================================
        -- Listing concentration by host type
        -- ============================================================
        round(
            100.0 * listings_controlled_by_single_listing_hosts
            / nullif(listing_count, 0),
            2
        ) as single_listing_host_listing_share_pct,

        round(
            100.0 * listings_controlled_by_multi_listing_hosts
            / nullif(listing_count, 0),
            2
        ) as multi_listing_host_listing_share_pct,

        -- ============================================================
        -- Host characteristics
        -- ============================================================
        round(
            100.0 * superhost_count
            / nullif(host_count, 0),
            2
        ) as superhost_share_pct,

        round(
            100.0 * identity_verified_host_count
            / nullif(host_count, 0),
            2
        ) as identity_verified_host_share_pct

    from aggregated

)

select *
from final