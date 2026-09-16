select *

from {{ ref('int_host_snapshot') }}

where
    observed_listing_count <= 0

    or observed_entire_home_listing_count < 0
    or observed_private_room_listing_count < 0
    or observed_shared_room_listing_count < 0

    or listings_with_price < 0
    or listings_with_price > observed_listing_count

    or (
        observed_entire_home_listing_count
        + observed_private_room_listing_count
        + observed_shared_room_listing_count
        > observed_listing_count
    )

    or (
        observed_host_segment = '1'
        and observed_listing_count <> 1
    )

    or (
        observed_host_segment = '2-5'
        and observed_listing_count not between 2 and 5
    )

    or (
        observed_host_segment = '6-10'
        and observed_listing_count not between 6 and 10
    )

    or (
        observed_host_segment = '11-20'
        and observed_listing_count not between 11 and 20
    )

    or (
        observed_host_segment = '21+'
        and observed_listing_count <= 20
    )

    or is_observed_multi_listing_host
        <> (observed_listing_count > 1)

    or calculated_vs_observed_listing_difference
        <> inside_airbnb_calculated_host_listings_count
         - observed_listing_count