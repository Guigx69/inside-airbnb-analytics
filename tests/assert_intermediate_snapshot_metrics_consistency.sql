select
    'int_listing_snapshot' as model_name,
    source_country,
    source_city,
    listing_id

from {{ ref('int_listing_snapshot') }}

where
       snapshot_sequence < 1
    or snapshot_count < 1
    or (
        missing_snapshot_count is not null
        and missing_snapshot_count < 0
    )
    or (
        previous_snapshot_sequence is not null
        and previous_snapshot_sequence >= snapshot_sequence
    )
    or (
        previous_snapshot_sequence is not null
        and missing_snapshot_count
            <> snapshot_sequence - previous_snapshot_sequence - 1
    )
    or (
        missing_snapshot_count is not null
        and has_observation_gap <> (missing_snapshot_count > 0)
    )

union all

select
    'int_reviews' as model_name,
    source_country,
    source_city,
    listing_id

from {{ ref('int_reviews') }}

where snapshot_count < 1