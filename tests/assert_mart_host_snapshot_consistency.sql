select
    *
from {{ ref('mart_host_snapshot') }}
where

    -- ============================================================
    -- La segmentation des hôtes doit reconstituer la population des hôtes
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
    -- Les types d'hôtes doivent reconstituer la population des annonces
    -- ============================================================
    or listings_controlled_by_single_listing_hosts
        + listings_controlled_by_multi_listing_hosts
        <> listing_count

    -- ============================================================
    -- Les volumes de concentration doivent être monotones
    -- ============================================================
    or listings_controlled_by_top_1_pct_hosts
        > listings_controlled_by_top_5_pct_hosts

    or listings_controlled_by_top_5_pct_hosts
        > listings_controlled_by_top_10_pct_hosts

    or listings_controlled_by_top_10_pct_hosts
        > listing_count

    -- ============================================================
    -- Les parts de concentration doivent être monotones et bornées
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
    -- Le HHI doit être valide
    -- ============================================================
    or host_hhi < 0
    or host_hhi > 10000