with invalid_rows as (

    select *
    from {{ ref('mart_price_distribution_snapshot') }}

    where
        -- Population
        listing_count < 0

        or listings_with_price < 0

        or listings_with_price > listing_count

        -- Shares
        or market_listing_share_pct < 0
        or market_listing_share_pct > 100

        or (
            priced_listing_share_pct is not null
            and (
                priced_listing_share_pct < 0
                or priced_listing_share_pct > 100
            )
        )

        -- NO_PRICE semantics
        or (
            price_band = 'NO_PRICE'
            and (
                listings_with_price <> 0
                or min_price is not null
                or max_price is not null
                or average_price is not null
                or median_price is not null
            )
        )

        -- Les tranches tarifaires doivent contenir uniquement des annonces avec prix
        or (
            price_band <> 'NO_PRICE'
            and listings_with_price <> listing_count
        )

        -- Limites des tranches tarifaires
        or (
            price_band = '01_<50'
            and (
                min_price >= 50
                or max_price >= 50
            )
        )

        or (
            price_band = '02_50_99'
            and (
                min_price < 50
                or max_price >= 100
            )
        )

        or (
            price_band = '03_100_149'
            and (
                min_price < 100
                or max_price >= 150
            )
        )

        or (
            price_band = '04_150_199'
            and (
                min_price < 150
                or max_price >= 200
            )
        )

        or (
            price_band = '05_200_299'
            and (
                min_price < 200
                or max_price >= 300
            )
        )

        or (
            price_band = '06_300_PLUS'
            and min_price < 300
        )

        -- Cohérence des fenêtres d'avis
        or reconstructed_review_count_l30d < 0
        or reconstructed_review_count_l90d < 0
        or reconstructed_review_count_l365d < 0

        or reconstructed_review_count_l30d
            > reconstructed_review_count_l90d

        or reconstructed_review_count_l90d
            > reconstructed_review_count_l365d

)

select *
from invalid_rows