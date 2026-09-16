select
    source_country,
    source_city,
    snapshot_date,
    listing_id,
    review_count_l30d,
    review_count_l90d,
    review_count_l365d,
    review_count_to_snapshot,
    first_review_date_to_snapshot,
    last_review_date_to_snapshot,
    days_since_last_review,
    has_reviews_to_snapshot,
    has_review_l30d,
    has_review_l90d,
    has_review_l365d

from {{ ref('int_listing_review_metrics') }}

where
       review_count_l30d < 0
    or review_count_l90d < 0
    or review_count_l365d < 0
    or review_count_to_snapshot < 0

    -- Nested temporal windows
    or review_count_l30d > review_count_l90d
    or review_count_l90d > review_count_l365d
    or review_count_l365d > review_count_to_snapshot

    -- No review means no review dates or recency metric
    or (
        review_count_to_snapshot = 0
        and (
            first_review_date_to_snapshot is not null
            or last_review_date_to_snapshot is not null
            or days_since_last_review is not null
        )
    )

    -- At least one review means dates and recency must exist
    or (
        review_count_to_snapshot > 0
        and (
            first_review_date_to_snapshot is null
            or last_review_date_to_snapshot is null
            or days_since_last_review is null
        )
    )

    -- Review dates cannot be after the analytical snapshot
    or first_review_date_to_snapshot > snapshot_date
    or last_review_date_to_snapshot > snapshot_date

    -- First review cannot be after last review
    or first_review_date_to_snapshot > last_review_date_to_snapshot

    -- Boolean flags must agree with their corresponding counters
    or has_reviews_to_snapshot
        <> (review_count_to_snapshot > 0)

    or has_review_l30d
        <> (review_count_l30d > 0)

    or has_review_l90d
        <> (review_count_l90d > 0)

    or has_review_l365d
        <> (review_count_l365d > 0)