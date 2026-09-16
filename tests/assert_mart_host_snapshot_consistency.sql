select
    *
from {{ ref('mart_host_snapshot') }}
where

    -- ============================================================
    -- Host segmentation must reconstruct the host population
    -- ============================================================
    single_listing_host_count
        + host_count_2_to_5
        + host_count_6_to_10
        + host_count_11_to_20
        + host_count_21_plus
        <> host_count

    or single_listing_host_count
        + multi_listing_host_count
        <> host_count

    -- ============================================================
    -- Host type must reconstruct the listing population
    -- ============================================================
    or listings_controlled_by_single_listing_hosts
        + listings_controlled_by_multi_listing_hosts
        <> listing_count

    -- ============================================================
    -- Concentration volumes must be monotonic
    -- ============================================================
    or listings_controlled_by_top_1_pct_hosts
        > listings_controlled_by_top_5_pct_hosts

    or listings_controlled_by_top_5_pct_hosts
        > listings_controlled_by_top_10_pct_hosts

    or listings_controlled_by_top_10_pct_hosts
        > listing_count

    -- ============================================================
    -- Concentration shares must be monotonic and bounded
    -- ============================================================
    or top_1_pct_listing_share_pct < 0
    or top_1_pct_listing_share_pct > 100

    or top_5_pct_listing_share_pct < 0
    or top_5_pct_listing_share_pct > 100

    or top_10_pct_listing_share_pct < 0
    or top_10_pct_listing_share_pct > 100

    or top_1_pct_listing_share_pct
        > top_5_pct_listing_share_pct

    or top_5_pct_listing_share_pct
        > top_10_pct_listing_share_pct

    -- ============================================================
    -- HHI must be valid
    -- ============================================================
    or host_hhi < 0
    or host_hhi > 10000