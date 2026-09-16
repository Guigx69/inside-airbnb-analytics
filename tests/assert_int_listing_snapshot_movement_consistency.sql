select *
from {{ ref('int_listing_snapshot_movement') }}

where
       snapshot_count <= 0

    or first_seen_snapshot > snapshot_date

    or (
        movement_status = 'baseline'
        and market_previous_snapshot_date is not null
    )

    or (
        movement_status <> 'baseline'
        and market_previous_snapshot_date is null
    )

    or (
        movement_status = 'baseline'
        and was_present_previous_snapshot
    )

    or (
        movement_status = 'retained'
        and not was_present_previous_snapshot
    )

    or (
        movement_status in ('newly_observed', 'returned_after_gap')
        and was_present_previous_snapshot
    )

    or (
        movement_status = 'newly_observed'
        and first_seen_snapshot <> snapshot_date
    )

    or (
        movement_status = 'returned_after_gap'
        and first_seen_snapshot >= snapshot_date
    )