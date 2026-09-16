select *
from {{ ref('mart_price_transition') }}
where

    -- Population
    listing_observation_count <= 0

    or listings_with_previous_price < 0
    or listings_with_current_price < 0
    or comparable_listing_count < 0

    or listings_with_previous_price > listing_observation_count
    or listings_with_current_price > listing_observation_count
    or comparable_listing_count > listing_observation_count

    or comparable_listing_count > listings_with_previous_price
    or comparable_listing_count > listings_with_current_price

    -- Every comparable listing must belong to exactly one price movement
    or (
        price_increase_count
        + price_decrease_count
        + unchanged_price_count
    ) <> comparable_listing_count

    -- Transition semantics
    or (
        transition_type = 'CONSECUTIVE'
        and missing_snapshot_count <> 0
    )

    or (
        transition_type = 'AFTER_GAP'
        and missing_snapshot_count <= 0
    )

    or transition_type not in ('CONSECUTIVE', 'AFTER_GAP')

    -- Coverage
    or comparable_price_coverage_pct < 0
    or comparable_price_coverage_pct > 100

    -- When comparable listings exist, shares must reconcile to 100%
    or (
        comparable_listing_count > 0
        and abs(
            price_increase_share_pct
            + price_decrease_share_pct
            + unchanged_price_share_pct
            - 100
        ) > 0.02
    )

    -- When there is no comparable price, analytical price metrics
    -- must remain NULL rather than represent artificial zero values
    or (
        comparable_listing_count = 0
        and (
            price_increase_share_pct is not null
            or price_decrease_share_pct is not null
            or unchanged_price_share_pct is not null
            or average_previous_price is not null
            or average_current_price is not null
            or median_previous_price is not null
            or median_current_price is not null
            or average_price_change is not null
            or median_price_change is not null
            or average_price_change_pct is not null
            or median_price_change_pct is not null
        )
    )

    -- When comparable prices exist, core price metrics must exist
    or (
        comparable_listing_count > 0
        and (
            price_increase_share_pct is null
            or price_decrease_share_pct is null
            or unchanged_price_share_pct is null
            or average_previous_price is null
            or average_current_price is null
            or median_previous_price is null
            or median_current_price is null
            or average_price_change is null
            or median_price_change is null
            or average_price_change_pct is null
            or median_price_change_pct is null
        )
    )