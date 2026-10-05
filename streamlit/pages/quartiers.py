
import altair as alt
import pandas as pd
import streamlit as st

from ui.components import (
    insight_box,
    kpi_grid,
    note,
    page_header,
    section_header,
    transition_grid,
)
from ui.formatters import (
    format_currency,
    format_date_fr,
    format_integer,
    format_percent,
)
from ui.config import MARTS, get_session
from ui.sidebar import render_sidebar
from ui.styles import apply_global_styles


# ============================================================
# Global styles
# ============================================================

apply_global_styles()


# ============================================================
# Snowflake connection
# ============================================================

session = get_session()


# ============================================================
# Data loading
# ============================================================

@st.cache_data(ttl=3600)
def load_price_data():

    market = session.sql(f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            LISTING_COUNT,
            LISTINGS_WITH_PRICE,
            AVERAGE_PRICE,
            MEDIAN_PRICE
        FROM {MARTS}.MART_MARKET_SNAPSHOT
        WHERE LOWER(SOURCE_COUNTRY) = 'france'
          AND LOWER(SOURCE_CITY) = 'lyon'
        ORDER BY SNAPSHOT_DATE
    """).to_pandas()

    distribution = session.sql(f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            PRICE_BAND,
            PRICE_BAND_ORDER,
            LISTING_COUNT,
            LISTINGS_WITH_PRICE,
            AVERAGE_PRICE,
            MEDIAN_PRICE,
            MIN_PRICE,
            MAX_PRICE,
            MARKET_LISTING_SHARE_PCT,
            PRICED_LISTING_SHARE_PCT
        FROM {MARTS}.MART_PRICE_DISTRIBUTION_SNAPSHOT
        WHERE LOWER(SOURCE_COUNTRY) = 'france'
          AND LOWER(SOURCE_CITY) = 'lyon'
        ORDER BY
            SNAPSHOT_DATE,
            PRICE_BAND_ORDER
    """).to_pandas()

    transitions = session.sql(f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            PREVIOUS_SNAPSHOT_DATE,
            SNAPSHOT_DATE,
            DAYS_BETWEEN_OBSERVATIONS,
            TRANSITION_TYPE,
            MISSING_SNAPSHOT_COUNT,
            LISTING_OBSERVATION_COUNT,
            LISTINGS_WITH_PREVIOUS_PRICE,
            LISTINGS_WITH_CURRENT_PRICE,
            COMPARABLE_LISTING_COUNT,
            PRICE_INCREASE_COUNT,
            PRICE_DECREASE_COUNT,
            UNCHANGED_PRICE_COUNT,
            AVERAGE_PREVIOUS_PRICE,
            AVERAGE_CURRENT_PRICE,
            MEDIAN_PREVIOUS_PRICE,
            MEDIAN_CURRENT_PRICE,
            AVERAGE_PRICE_CHANGE,
            MEDIAN_PRICE_CHANGE,
            AVERAGE_PRICE_CHANGE_PCT,
            MEDIAN_PRICE_CHANGE_PCT,
            COMPARABLE_PRICE_COVERAGE_PCT,
            PRICE_INCREASE_SHARE_PCT,
            PRICE_DECREASE_SHARE_PCT,
            UNCHANGED_PRICE_SHARE_PCT
        FROM {MARTS}.MART_PRICE_TRANSITION
        WHERE LOWER(SOURCE_COUNTRY) = 'france'
          AND LOWER(SOURCE_CITY) = 'lyon'
        ORDER BY
            SNAPSHOT_DATE,
            PREVIOUS_SNAPSHOT_DATE
    """).to_pandas()

    for dataframe in [
        market,
        distribution,
        transitions,
    ]:
        dataframe.columns = dataframe.columns.str.lower()

    market["snapshot_date"] = pd.to_datetime(
        market["snapshot_date"]
    )

    distribution["snapshot_date"] = pd.to_datetime(
        distribution["snapshot_date"]
    )

    transitions["snapshot_date"] = pd.to_datetime(
        transitions["snapshot_date"]
    )

    transitions["previous_snapshot_date"] = pd.to_datetime(
        transitions["previous_snapshot_date"]
    )

    return market, distribution, transitions


market, distribution, transitions = load_price_data()


# ============================================================
# Snapshot / sidebar
# ============================================================

snapshot_dates = sorted(
    market["snapshot_date"].unique().tolist()
)

selected_snapshot = render_sidebar(
    snapshot_dates=snapshot_dates,
)

selected_snapshot = pd.Timestamp(selected_snapshot)

current = market[
    market["snapshot_date"] == selected_snapshot
].copy()

current_distribution = distribution[
    distribution["snapshot_date"] == selected_snapshot
].copy()


if current.empty:

    st.error(
        "Aucune donnée marché n'est disponible "
        "pour l'observation sélectionnée."
    )

    st.stop()


current = current.iloc[0]


# ============================================================
# Derived indicators
# ============================================================

listing_count = int(current["listing_count"])
listings_with_price = int(current["listings_with_price"])

price_coverage_pct = (
    100.0
    * listings_with_price
    / listing_count
    if listing_count > 0
    else 0.0
)

average_price = current["average_price"]
median_price = current["median_price"]

has_price_data = (
    listings_with_price > 0
    and pd.notna(average_price)
    and pd.notna(median_price)
)


# ============================================================
# Header
# ============================================================

page_header(
    title="Prix",
    subtitle=(
        "Niveaux de prix observés à Lyon, distribution tarifaire "
        "et évolution à annonces comparables."
    ),
    icon="💶",
    badges=[
        "🇫🇷 Lyon, France",
        f"🗓️ {format_date_fr(selected_snapshot)}",
        f"📁 {format_integer(len(snapshot_dates))} observations historiques",
    ],
)


# ============================================================
# Price overview
# ============================================================

section_header(
    "Niveau des prix",
    (
        f"Situation tarifaire du marché observé "
        f"au {format_date_fr(selected_snapshot)}."
    ),
)


kpi_grid(
    [
        {
            "label": "Prix médian",
            "value": (
                format_currency(median_price)
                if has_price_data
                else "N/D"
            ),
            "detail": (
                "Parmi les annonces disposant d'un prix"
                if has_price_data
                else "Aucune information tarifaire"
            ),
        },
        {
            "label": "Prix moyen",
            "value": (
                format_currency(average_price)
                if has_price_data
                else "N/D"
            ),
            "detail": (
                "Parmi les annonces disposant d'un prix"
                if has_price_data
                else "Aucune information tarifaire"
            ),
        },
        {
            "label": "Annonces avec prix",
            "value": format_integer(listings_with_price),
            "detail": (
                f"sur {format_integer(listing_count)} "
                f"annonces observées"
            ),
        },
        {
            "label": "Couverture tarifaire",
            "value": format_percent(price_coverage_pct),
            "detail": (
                "Part du marché disposant "
                "d'un prix exploitable"
            ),
        },
    ],
    columns=2,
)


if has_price_data:

    insight_box(
        (
            f"Couverture tarifaire · "
            f"{format_percent(price_coverage_pct)}"
        ),
        (
            f"Les statistiques de prix portent sur "
            f"{format_integer(listings_with_price)} annonces parmi "
            f"les {format_integer(listing_count)} observées. "
            f"Les niveaux tarifaires doivent donc être interprétés "
            f"en tenant compte de cette couverture."
        ),
    )

else:

    insight_box(
        "Aucune donnée tarifaire exploitable",
        (
            f"L'observation du {format_date_fr(selected_snapshot)} "
            f"contient {format_integer(listing_count)} annonces, "
            f"mais aucune information de prix exploitable. "
            f"L'absence de prix ne correspond pas à un prix de 0 €."
        ),
    )


# ============================================================
# Price distribution
# ============================================================

st.divider()

section_header(
    "Distribution des prix",
    (
        "Répartition des annonces disposant d'un prix "
        "selon leur tranche tarifaire."
    ),
)


priced_distribution = current_distribution[
    current_distribution["price_band_order"] > 0
].copy()

priced_distribution = priced_distribution.sort_values(
    "price_band_order"
)


price_band_labels = {
    "01_<50": "< 50 €",
    "02_50_99": "50–99 €",
    "03_100_149": "100–149 €",
    "04_150_199": "150–199 €",
    "05_200_299": "200–299 €",
    "06_300_PLUS": "300 € et +",
}


if has_price_data and not priced_distribution.empty:

    priced_distribution["price_band_label"] = (
        priced_distribution["price_band"].map(
            price_band_labels
        )
    )

    priced_distribution["price_band_label"] = (
        priced_distribution["price_band_label"]
        .fillna(
            priced_distribution["price_band"]
        )
    )

    priced_distribution["chart_label"] = (
        priced_distribution.apply(
            lambda row: (
                f"{format_integer(row['listing_count'])} · "
                f"{format_percent(row['priced_listing_share_pct'])}"
            ),
            axis=1,
        )
    )

    price_band_order = (
        priced_distribution
        .sort_values("price_band_order")[
            "price_band_label"
        ]
        .tolist()
    )


    distribution_bars = (
        alt.Chart(priced_distribution)
        .mark_bar(
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4,
            size=42,
        )
        .encode(
            x=alt.X(
                "price_band_label:N",
                title=None,
                sort=price_band_order,
                axis=alt.Axis(
                    labelAngle=0,
                    labelPadding=10,
                    labelLimit=120,
                ),
            ),
            y=alt.Y(
                "listing_count:Q",
                title="Nombre d'annonces",
                axis=alt.Axis(
                    format=",d",
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "price_band_label:N",
                    title="Tranche",
                ),
                alt.Tooltip(
                    "listing_count:Q",
                    title="Annonces",
                    format=",d",
                ),
                alt.Tooltip(
                    "priced_listing_share_pct:Q",
                    title="Part des annonces tarifées",
                    format=".1f",
                ),
                alt.Tooltip(
                    "average_price:Q",
                    title="Prix moyen",
                    format=".2f",
                ),
                alt.Tooltip(
                    "median_price:Q",
                    title="Prix médian",
                    format=".2f",
                ),
            ],
        )
        .properties(
            height=330,
        )
    )


    distribution_labels = (
        alt.Chart(priced_distribution)
        .mark_text(
            dy=-10,
            fontSize=12,
        )
        .encode(
            x=alt.X(
                "price_band_label:N",
                sort=price_band_order,
            ),
            y=alt.Y(
                "listing_count:Q",
            ),
            text=alt.Text(
                "chart_label:N",
            ),
        )
    )


    st.altair_chart(
        distribution_bars + distribution_labels,
        use_container_width=True,
    )


    note(
        "Les pourcentages représentent la part de chaque tranche "
        "parmi les annonces disposant d'un prix. Les annonces sans "
        "prix sont exclues de cette distribution."
    )


    # ========================================================
    # Distribution details
    # ========================================================

    st.write("")

    section_header(
        "Détail des tranches tarifaires",
        (
            "Volume, poids et niveaux de prix "
            "au sein de chaque tranche."
        ),
    )


    price_detail = priced_distribution[
        [
            "price_band_label",
            "listing_count",
            "priced_listing_share_pct",
            "average_price",
            "median_price",
            "min_price",
            "max_price",
        ]
    ].copy()


    price_detail = price_detail.rename(
        columns={
            "price_band_label": "Tranche de prix",
            "listing_count": "Annonces",
            "priced_listing_share_pct": "Part tarifée (%)",
            "average_price": "Prix moyen (€)",
            "median_price": "Prix médian (€)",
            "min_price": "Minimum (€)",
            "max_price": "Maximum (€)",
        }
    )


    price_detail["Annonces"] = (
        price_detail["Annonces"]
        .apply(format_integer)
    )

    price_detail["Part tarifée (%)"] = (
        price_detail["Part tarifée (%)"]
        .apply(format_percent)
    )

    for column in [
        "Prix moyen (€)",
        "Prix médian (€)",
        "Minimum (€)",
        "Maximum (€)",
    ]:

        price_detail[column] = (
            price_detail[column]
            .apply(
                lambda value: format_currency(
                    value,
                    decimals=2,
                )
            )
        )


    st.dataframe(
        price_detail,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Tranche de prix": st.column_config.TextColumn(
                width="medium",
            ),
        },
    )


else:

    st.info(
        "Aucune distribution tarifaire n'est disponible "
        "pour cette observation."
    )


# ============================================================
# Historical price evolution
# ============================================================

st.divider()

section_header(
    "Évolution historique des prix",
    (
        "Évolution du prix moyen et du prix médian "
        "sur les observations disposant d'une information tarifaire."
    ),
)


price_history = market[
    market["listings_with_price"] > 0
].copy()

price_history = price_history[
    price_history["average_price"].notna()
    & price_history["median_price"].notna()
].copy()

price_history = price_history.sort_values(
    "snapshot_date"
)


if not price_history.empty:

    price_history["date_label"] = (
        price_history["snapshot_date"]
        .apply(format_date_fr)
    )

    date_order = (
        market
        .sort_values("snapshot_date")[
            "snapshot_date"
        ]
        .apply(format_date_fr)
        .tolist()
    )


    price_history_long = price_history.melt(
        id_vars=[
            "snapshot_date",
            "date_label",
        ],
        value_vars=[
            "average_price",
            "median_price",
        ],
        var_name="indicator",
        value_name="price",
    )


    price_history_long["indicator_label"] = (
        price_history_long["indicator"].map(
            {
                "average_price": "Prix moyen",
                "median_price": "Prix médian",
            }
        )
    )


    historical_chart = (
        alt.Chart(price_history_long)
        .mark_line(
            point=True,
            strokeWidth=3,
        )
        .encode(
            x=alt.X(
                "date_label:N",
                title=None,
                sort=date_order,
                axis=alt.Axis(
                    labelAngle=0,
                    labelPadding=10,
                ),
            ),
            y=alt.Y(
                "price:Q",
                title="Prix (€)",
                scale=alt.Scale(
                    zero=False,
                ),
            ),
            color=alt.Color(
                "indicator_label:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Prix moyen",
                        "Prix médian",
                    ],
                    range=[
                        "#2563EB",
                        "#60A5FA",
                    ],
                ),
                legend=alt.Legend(
                    orient="bottom",
                    direction="horizontal",
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "date_label:N",
                    title="Observation",
                ),
                alt.Tooltip(
                    "indicator_label:N",
                    title="Indicateur",
                ),
                alt.Tooltip(
                    "price:Q",
                    title="Prix",
                    format=".2f",
                ),
            ],
        )
        .properties(
            height=320,
        )
    )


    st.altair_chart(
        historical_chart,
        use_container_width=True,
    )


else:

    st.info(
        "Aucun historique tarifaire exploitable n'est disponible."
    )


# ============================================================
# Historical price coverage
# ============================================================

st.write("")

section_header(
    "Couverture tarifaire historique",
    (
        "Part des annonces disposant d'un prix "
        "pour chaque observation."
    ),
)


coverage_history = market.copy()

coverage_history["price_coverage_pct"] = (
    100.0
    * coverage_history["listings_with_price"]
    / coverage_history["listing_count"]
)

coverage_history["date_label"] = (
    coverage_history["snapshot_date"]
    .apply(format_date_fr)
)

coverage_history["coverage_label"] = (
    coverage_history["price_coverage_pct"]
    .apply(format_percent)
)

coverage_history = coverage_history.sort_values(
    "snapshot_date"
)

coverage_date_order = (
    coverage_history["date_label"].tolist()
)


coverage_bars = (
    alt.Chart(coverage_history)
    .mark_bar(
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
        size=52,
    )
    .encode(
        x=alt.X(
            "date_label:N",
            title=None,
            sort=coverage_date_order,
            axis=alt.Axis(
                labelAngle=0,
                labelPadding=10,
            ),
        ),
        y=alt.Y(
            "price_coverage_pct:Q",
            title="Couverture tarifaire (%)",
            scale=alt.Scale(
                domain=[0, 100],
            ),
        ),
        color=alt.condition(
            alt.datum.price_coverage_pct > 0,
            alt.value("#2563EB"),
            alt.value("#D1D5DB"),
        ),
        tooltip=[
            alt.Tooltip(
                "date_label:N",
                title="Observation",
            ),
            alt.Tooltip(
                "listing_count:Q",
                title="Annonces observées",
                format=",d",
            ),
            alt.Tooltip(
                "listings_with_price:Q",
                title="Annonces avec prix",
                format=",d",
            ),
            alt.Tooltip(
                "price_coverage_pct:Q",
                title="Couverture",
                format=".1f",
            ),
        ],
    )
    .properties(
        height=280,
    )
)


coverage_labels = (
    alt.Chart(coverage_history)
    .mark_text(
        dy=-10,
        fontSize=12,
    )
    .encode(
        x=alt.X(
            "date_label:N",
            sort=coverage_date_order,
        ),
        y=alt.Y(
            "price_coverage_pct:Q",
        ),
        text=alt.Text(
            "coverage_label:N",
        ),
    )
)


st.altair_chart(
    coverage_bars + coverage_labels,
    use_container_width=True,
)


note(
    "L'observation du 22/12/2025 ne contient aucune information "
    "tarifaire. Cette absence de données ne correspond pas à "
    "un niveau de prix égal à 0 €."
)


# ============================================================
# Comparable price transition
# ============================================================

st.divider()

section_header(
    "Évolution à annonces comparables",
    (
        "Évolution des prix pour les annonces disposant "
        "d'un prix dans deux observations consécutives."
    ),
)


current_transition = transitions[
    (
        transitions["snapshot_date"]
        == selected_snapshot
    )
    & (
        transitions["transition_type"]
        .astype(str)
        .str.upper()
        == "CONSECUTIVE"
    )
].copy()


if current_transition.empty:

    insight_box(
        "Aucune comparaison consécutive disponible",
        (
            "Cette observation ne dispose pas d'une transition "
            "consécutive exploitable pour comparer les prix "
            "à population comparable."
        ),
    )


else:

    current_transition = (
        current_transition
        .sort_values(
            "previous_snapshot_date",
            ascending=False,
        )
        .iloc[0]
    )


    previous_snapshot_date = (
        current_transition[
            "previous_snapshot_date"
        ]
    )

    comparable_listing_count = (
        current_transition[
            "comparable_listing_count"
        ]
    )

    comparable_coverage_pct = (
        current_transition[
            "comparable_price_coverage_pct"
        ]
    )


    insight_box(
        (
            f"Du {format_date_fr(previous_snapshot_date)} "
            f"au {format_date_fr(selected_snapshot)}"
        ),
        (
            f"L'analyse porte sur "
            f"{format_integer(comparable_listing_count)} annonces "
            f"disposant d'un prix exploitable dans les deux "
            f"observations consécutives, soit une couverture "
            f"comparable de "
            f"{format_percent(comparable_coverage_pct)}."
        ),
    )


    kpi_grid(
        [
            {
                "label": "Annonces comparables",
                "value": format_integer(
                    comparable_listing_count
                ),
                "detail": (
                    f"Couverture : "
                    f"{format_percent(comparable_coverage_pct)}"
                ),
            },
            {
                "label": "Prix médian précédent",
                "value": format_currency(
                    current_transition[
                        "median_previous_price"
                    ]
                ),
                "detail": format_date_fr(
                    previous_snapshot_date
                ),
            },
            {
                "label": "Prix médian actuel",
                "value": format_currency(
                    current_transition[
                        "median_current_price"
                    ]
                ),
                "detail": format_date_fr(
                    selected_snapshot
                ),
            },
            {
                "label": "Variation médiane",
                "value": format_currency(
                    current_transition[
                        "median_price_change"
                    ],
                    decimals=2,
                ),
                "detail": (
                    f"{format_percent(current_transition['median_price_change_pct'])} "
                    f"par rapport à l'observation précédente"
                ),
            },
        ],
        columns=2,
    )


    # ========================================================
    # Direction of price movements
    # ========================================================

    st.write("")

    section_header(
        "Sens des évolutions",
        (
            "Répartition des annonces comparables selon "
            "l'évolution de leur prix."
        ),
    )


    price_movements = pd.DataFrame(
        {
            "movement": [
                "En hausse",
                "En baisse",
                "Inchangé",
            ],
            "count": [
                current_transition[
                    "price_increase_count"
                ],
                current_transition[
                    "price_decrease_count"
                ],
                current_transition[
                    "unchanged_price_count"
                ],
            ],
            "share_pct": [
                current_transition[
                    "price_increase_share_pct"
                ],
                current_transition[
                    "price_decrease_share_pct"
                ],
                current_transition[
                    "unchanged_price_share_pct"
                ],
            ],
        }
    )


    price_movements["label"] = (
        price_movements.apply(
            lambda row: (
                f"{format_integer(row['count'])} · "
                f"{format_percent(row['share_pct'])}"
            ),
            axis=1,
        )
    )


    movement_order = [
        "En hausse",
        "En baisse",
        "Inchangé",
    ]


    movement_bars = (
        alt.Chart(price_movements)
        .mark_bar(
            cornerRadiusEnd=4,
            size=28,
        )
        .encode(
            y=alt.Y(
                "movement:N",
                title=None,
                sort=movement_order,
                axis=alt.Axis(
                    labelPadding=10,
                ),
            ),
            x=alt.X(
                "count:Q",
                title="Nombre d'annonces comparables",
            ),
            color=alt.Color(
                "movement:N",
                title=None,
                scale=alt.Scale(
                    domain=movement_order,
                    range=[
                        "#2563EB",
                        "#EF4444",
                        "#9CA3AF",
                    ],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip(
                    "movement:N",
                    title="Évolution",
                ),
                alt.Tooltip(
                    "count:Q",
                    title="Annonces",
                    format=",d",
                ),
                alt.Tooltip(
                    "share_pct:Q",
                    title="Part",
                    format=".1f",
                ),
            ],
        )
        .properties(
            height=220,
        )
    )


    movement_labels = (
        alt.Chart(price_movements)
        .mark_text(
            align="left",
            baseline="middle",
            dx=8,
            fontSize=12,
        )
        .encode(
            y=alt.Y(
                "movement:N",
                sort=movement_order,
            ),
            x=alt.X(
                "count:Q",
            ),
            text=alt.Text(
                "label:N",
            ),
        )
    )


    st.altair_chart(
        movement_bars + movement_labels,
        use_container_width=True,
    )


    transition_grid(
        [
            {
                "label": "En hausse",
                "value": format_integer(
                    current_transition[
                        "price_increase_count"
                    ]
                ),
                "detail": (
                    f"{format_percent(current_transition['price_increase_share_pct'])} "
                    f"des annonces comparables"
                ),
            },
            {
                "label": "En baisse",
                "value": format_integer(
                    current_transition[
                        "price_decrease_count"
                    ]
                ),
                "detail": (
                    f"{format_percent(current_transition['price_decrease_share_pct'])} "
                    f"des annonces comparables"
                ),
            },
            {
                "label": "Inchangé",
                "value": format_integer(
                    current_transition[
                        "unchanged_price_count"
                    ]
                ),
                "detail": (
                    f"{format_percent(current_transition['unchanged_price_share_pct'])} "
                    f"des annonces comparables"
                ),
            },
            {
                "label": "Écart moyen",
                "value": format_currency(
                    current_transition[
                        "average_price_change"
                    ],
                    decimals=2,
                ),
                "detail": (
                    f"{format_percent(current_transition['average_price_change_pct'])} "
                    f"en moyenne"
                ),
            },
        ],
        columns=2,
    )


    note(
        "La comparaison porte uniquement sur les annonces disposant "
        "d'un prix dans deux observations consécutives. Les transitions "
        "de type AFTER_GAP sont volontairement exclues afin de ne pas "
        "mélanger des périodes comportant des observations manquantes."
    )


# ============================================================
# Methodological note
# ============================================================

st.write("")

with st.expander(
    "Comment interpréter les prix ?"
):

    st.markdown(
        """
**Prix moyen et médian**

Les indicateurs tarifaires portent uniquement sur les annonces pour
lesquelles Inside Airbnb fournit un prix exploitable. Le prix médian
est moins sensible aux valeurs extrêmes que le prix moyen.

**Couverture tarifaire**

La couverture correspond à la part des annonces observées disposant
d'un prix. Elle doit être prise en compte lors de toute comparaison
entre deux snapshots.

**Distribution**

Les tranches tarifaires sont calculées uniquement parmi les annonces
disposant d'un prix. Les annonces sans information tarifaire sont
exclues du graphique et du tableau de distribution.

**Comparaison à annonces comparables**

La comparaison utilise uniquement les transitions consécutives.
Une annonce doit disposer d'un prix dans les deux observations pour
être considérée comme comparable.

Les transitions après une absence (`AFTER_GAP`) sont exclues de cette
lecture afin de ne pas assimiler une comparaison espacée dans le temps
à une évolution entre deux snapshots successifs.

**Limite**

Le prix observé dans Inside Airbnb ne constitue ni un revenu réalisé,
ni un prix effectivement payé par un voyageur.
        """
    )