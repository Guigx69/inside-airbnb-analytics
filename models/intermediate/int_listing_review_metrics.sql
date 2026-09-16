with listing_snapshots as (

    /*
        One row per listing observation.

        This defines the analytical grain of the model:
        country / city / snapshot / listing.
    */
    select
        source_country,
        source_city,
        snapshot_date,
        listing_id

    from {{ ref('int_listing_snapshot') }}

),

reviews as (

    /*
        Business-level reviews deduplicated across the different
        Inside Airbnb source snapshots.

        A review can appear in several source snapshots, but
        int_reviews contains only one business-level occurrence.
    */
    select
        source_country,
        source_city,
        listing_id,
        review_id,
        review_date

    from {{ ref('int_reviews') }}

),

review_metrics as (

    select
        ls.source_country,
        ls.source_city,
        ls.snapshot_date,
        ls.listing_id,

        /*
            All review metrics below represent the review history
            known up to the listing snapshot date.

            Reviews dated after the snapshot are deliberately excluded.
        */
        count(r.review_id) as review_count_to_snapshot,

        count_if(
            r.review_date between
                dateadd('day', -29, ls.snapshot_date)
                and ls.snapshot_date
        ) as review_count_l30d,

        count_if(
            r.review_date between
                dateadd('day', -89, ls.snapshot_date)
                and ls.snapshot_date
        ) as review_count_l90d,

        count_if(
            r.review_date between
                dateadd('day', -364, ls.snapshot_date)
                and ls.snapshot_date
        ) as review_count_l365d,

        min(r.review_date) as first_review_date_to_snapshot,
        max(r.review_date) as last_review_date_to_snapshot,

        datediff(
            'day',
            max(r.review_date),
            ls.snapshot_date
        ) as days_since_last_review

    from listing_snapshots ls

    left join reviews r
        on ls.source_country = r.source_country
       and ls.source_city = r.source_city
       and ls.listing_id = r.listing_id
       and r.review_date <= ls.snapshot_date

    group by
        ls.source_country,
        ls.source_city,
        ls.snapshot_date,
        ls.listing_id

),

final as (

    select
        *,

        review_count_to_snapshot > 0
            as has_reviews_to_snapshot,

        review_count_l30d > 0
            as has_review_l30d,

        review_count_l90d > 0
            as has_review_l90d,

        review_count_l365d > 0
            as has_review_l365d

    from review_metrics

)

select *
from final