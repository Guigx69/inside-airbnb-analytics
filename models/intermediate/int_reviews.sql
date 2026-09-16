with reviews as (

    select *
    from {{ ref('stg_reviews') }}

),

review_history as (

    select
        source_country,
        source_city,
        listing_id,
        review_id,

        review_date,
        reviewer_id,

        first_value(reviewer_name) over (
            partition by
                source_country,
                source_city,
                listing_id,
                review_id
            order by snapshot_date desc
        ) as reviewer_name,

        comments,

        min(snapshot_date) over (
            partition by
                source_country,
                source_city,
                listing_id,
                review_id
        ) as first_seen_snapshot,

        max(snapshot_date) over (
            partition by
                source_country,
                source_city,
                listing_id,
                review_id
        ) as last_seen_snapshot,

        count(*) over (
            partition by
                source_country,
                source_city,
                listing_id,
                review_id
        ) as snapshot_count,

        row_number() over (
            partition by
                source_country,
                source_city,
                listing_id,
                review_id
            order by snapshot_date desc
        ) as version_rank

    from reviews

),

deduplicated as (

    select
        source_country,
        source_city,
        listing_id,
        review_id,
        review_date,
        reviewer_id,
        reviewer_name,
        comments,
        first_seen_snapshot,
        last_seen_snapshot,
        snapshot_count

    from review_history

    where version_rank = 1

)

select *
from deduplicated