with mart as (

    select *
    from {{ ref('mart_availability_horizon_snapshot') }}

),

source_metrics as (

    select
        source_country,
        source_city,
        snapshot_date,

        count(*) as expected_listing_count,

        min(availability_window_start_date)
            as expected_earliest_window_start_date,

        max(availability_window_start_date)
            as expected_latest_window_start_date,

        sum(represented_days_30d)
            as expected_represented_days_30d,

        sum(available_days_30d)
            as expected_available_days_30d,

        sum(represented_days_60d)
            as expected_represented_days_60d,

        sum(available_days_60d)
            as expected_available_days_60d,

        sum(represented_days_90d)
            as expected_represented_days_90d,

        sum(available_days_90d)
            as expected_available_days_90d,

        sum(represented_days_365d)
            as expected_represented_days_365d,

        sum(available_days_365d)
            as expected_available_days_365d

    from {{ ref('int_listing_availability_horizon') }}

    group by
        source_country,
        source_city,
        snapshot_date

)

select
    m.*

from mart m

left join source_metrics s
    on m.source_country = s.source_country
   and m.source_city = s.source_city
   and m.snapshot_date = s.snapshot_date

where
       s.snapshot_date is null

    -- Population
    or m.listing_count <> s.expected_listing_count

    -- Window boundaries
    or m.earliest_availability_window_start_date
        <> s.expected_earliest_window_start_date

    or m.latest_availability_window_start_date
        <> s.expected_latest_window_start_date

    -- Rapprochement avec la source
    or m.represented_days_30d
        <> s.expected_represented_days_30d

    or m.available_days_30d
        <> s.expected_available_days_30d

    or m.represented_days_60d
        <> s.expected_represented_days_60d

    or m.available_days_60d
        <> s.expected_available_days_60d

    or m.represented_days_90d
        <> s.expected_represented_days_90d

    or m.available_days_90d
        <> s.expected_available_days_90d

    or m.represented_days_365d
        <> s.expected_represented_days_365d

    or m.available_days_365d
        <> s.expected_available_days_365d

    -- La couverture de la source peut être partielle pour chaque horizon analytique.
    -- Les jours représentés doivent rester positifs et ne peuvent pas dépasser
    -- le maximum théorique de la population du snapshot.
    or m.represented_days_30d > m.listing_count * 30
    or m.represented_days_30d <= 0

    or m.represented_days_60d > m.listing_count * 60
    or m.represented_days_60d <= 0

    or m.represented_days_90d > m.listing_count * 90
    or m.represented_days_90d <= 0

    or m.represented_days_365d > m.listing_count * 365
    or m.represented_days_365d <= 0

    -- Les horizons représentés cumulés doivent être monotones.
    or m.represented_days_30d > m.represented_days_60d
    or m.represented_days_60d > m.represented_days_90d
    or m.represented_days_90d > m.represented_days_365d

    -- Les jours disponibles ne peuvent pas dépasser les jours représentés.
    or m.available_days_30d not between 0 and m.represented_days_30d
    or m.available_days_60d not between 0 and m.represented_days_60d
    or m.available_days_90d not between 0 and m.represented_days_90d
    or m.available_days_365d not between 0 and m.represented_days_365d

    -- Les horizons de disponibilité cumulés doivent être monotones.
    or m.available_days_30d > m.available_days_60d
    or m.available_days_60d > m.available_days_90d
    or m.available_days_90d > m.available_days_365d

    -- Tout pourcentage non nul doit rester dans les limites valides.
    or (
        m.market_availability_rate_30d_pct is not null
        and m.market_availability_rate_30d_pct not between 0 and 100
    )
    or (
        m.market_availability_rate_60d_pct is not null
        and m.market_availability_rate_60d_pct not between 0 and 100
    )
    or (
        m.market_availability_rate_90d_pct is not null
        and m.market_availability_rate_90d_pct not between 0 and 100
    )
    or (
        m.market_availability_rate_365d_pct is not null
        and m.market_availability_rate_365d_pct not between 0 and 100
    )

    or (
        m.average_listing_availability_rate_30d_pct is not null
        and m.average_listing_availability_rate_30d_pct not between 0 and 100
    )
    or (
        m.average_listing_availability_rate_60d_pct is not null
        and m.average_listing_availability_rate_60d_pct not between 0 and 100
    )
    or (
        m.average_listing_availability_rate_90d_pct is not null
        and m.average_listing_availability_rate_90d_pct not between 0 and 100
    )
    or (
        m.average_listing_availability_rate_365d_pct is not null
        and m.average_listing_availability_rate_365d_pct not between 0 and 100
    )

    or (
        m.median_listing_availability_rate_30d_pct is not null
        and m.median_listing_availability_rate_30d_pct not between 0 and 100
    )
    or (
        m.median_listing_availability_rate_60d_pct is not null
        and m.median_listing_availability_rate_60d_pct not between 0 and 100
    )
    or (
        m.median_listing_availability_rate_90d_pct is not null
        and m.median_listing_availability_rate_90d_pct not between 0 and 100
    )
    or (
        m.median_listing_availability_rate_365d_pct is not null
        and m.median_listing_availability_rate_365d_pct not between 0 and 100
    )

        -- Les taux du marché et les taux moyens des annonces doivent concorder dès que
    -- au moins une annonce dispose d'une couverture complète sur l'horizon.
    --
    -- Pour un horizon complet de N jours, chaque annonce éligible possède
    -- le même dénominateur N, donc :
    --
    --     SUM(available_days) / (N * listing_count)
    --       =
    --     AVG(available_days / N)
    --
    -- Les deux indicateurs doivent aussi être NULL lorsqu'aucune annonce n'a de couverture
    -- complète pour l'horizon correspondant.

    or (
        (
            m.market_availability_rate_30d_pct is null
            and m.average_listing_availability_rate_30d_pct is not null
        )
        or (
            m.market_availability_rate_30d_pct is not null
            and m.average_listing_availability_rate_30d_pct is null
        )
        or (
            m.market_availability_rate_30d_pct is not null
            and m.average_listing_availability_rate_30d_pct is not null
            and abs(
                m.market_availability_rate_30d_pct
                - m.average_listing_availability_rate_30d_pct
            ) > 0.01
        )
    )

    or (
        (
            m.market_availability_rate_60d_pct is null
            and m.average_listing_availability_rate_60d_pct is not null
        )
        or (
            m.market_availability_rate_60d_pct is not null
            and m.average_listing_availability_rate_60d_pct is null
        )
        or (
            m.market_availability_rate_60d_pct is not null
            and m.average_listing_availability_rate_60d_pct is not null
            and abs(
                m.market_availability_rate_60d_pct
                - m.average_listing_availability_rate_60d_pct
            ) > 0.01
        )
    )

    or (
        (
            m.market_availability_rate_90d_pct is null
            and m.average_listing_availability_rate_90d_pct is not null
        )
        or (
            m.market_availability_rate_90d_pct is not null
            and m.average_listing_availability_rate_90d_pct is null
        )
        or (
            m.market_availability_rate_90d_pct is not null
            and m.average_listing_availability_rate_90d_pct is not null
            and abs(
                m.market_availability_rate_90d_pct
                - m.average_listing_availability_rate_90d_pct
            ) > 0.01
        )
    )

    or (
        (
            m.market_availability_rate_365d_pct is null
            and m.average_listing_availability_rate_365d_pct is not null
        )
        or (
            m.market_availability_rate_365d_pct is not null
            and m.average_listing_availability_rate_365d_pct is null
        )
        or (
            m.market_availability_rate_365d_pct is not null
            and m.average_listing_availability_rate_365d_pct is not null
            and abs(
                m.market_availability_rate_365d_pct
                - m.average_listing_availability_rate_365d_pct
            ) > 0.01
        )
    )