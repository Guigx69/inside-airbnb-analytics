import os
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
    format_signed_currency,
    format_signed_percent,
)
from ui.sidebar import render_sidebar
from ui.styles import apply_global_styles


# ============================================================
# Global styles
# ============================================================

apply_global_styles()

# ============================================================
# Snowflake connection
# ============================================================

conn = st.connection(
    "snowflake",
    ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"),
)

session = conn.session()

# =============================================================================
# Configuration
# =============================================================================

MARKET_TABLE = "AIRBNB.DBT_GGILLET_MARTS.MART_MARKET_SNAPSHOT"

PRICE_DISTRIBUTION_TABLE = (
    "AIRBNB.DBT_GGILLET_MARTS.MART_PRICE_DISTRIBUTION_SNAPSHOT"
)

PRICE_TRANSITION_TABLE = (
    "AIRBNB.DBT_GGILLET_MARTS.MART_PRICE_TRANSITION"
)

CHART_BLUE = "#356DCC"
CHART_LIGHT_BLUE = "#79B8F3"
CHART_GREEN = "#2E8B57"
CHART_RED = "#D95C5C"
CHART_GREY = "#8A94A6"

PRICE_BAND_LABELS = {
    "01_<50": "< 50 €",
    "02_50_99": "50–99 €",
    "03_100_149": "100–149 €",
    "04_150_199": "150–199 €",
    "05_200_299": "200–299 €",
    "06_300_PLUS": "300 € et +",
    "NO_PRICE": "Sans prix",
}

# =============================================================================
# Helpers
# =============================================================================

def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Snowflake column names and snapshot dates."""

    if df.empty:
        return df

    result = df.copy()
    result.columns = result.columns.str.lower()

    for column in (
        "snapshot_date",
        "previous_snapshot_date",
    ):
        if column in result.columns:
            result[column] = pd.to_datetime(result[column])

    return result


def to_float(value, default=0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def to_int(value, default=0) -> int:
    if value is None or pd.isna(value):
        return default
    return int(value)


def format_price(value, decimals=0) -> str:
    if value is None or pd.isna(value):
        return "N/D"
    return format_currency(value, decimals=decimals)


def format_pct(value, decimals=1) -> str:
    if value is None or pd.isna(value):
        return "N/D"
    return format_percent(value, decimals=decimals)


def format_count(value) -> str:
    if value is None or pd.isna(value):
        return "N/D"
    return format_integer(value)


def format_price_band(value: str) -> str:
    if value is None:
        return "N/D"

    value = str(value)

    if value in PRICE_BAND_LABELS:
        return PRICE_BAND_LABELS[value]

    cleaned = (
        value.replace("_", " ")
        .replace("PLUS", "+")
        .strip()
    )

    return cleaned


def make_date_label(value) -> str:
    return format_date_fr(pd.to_datetime(value))

# =============================================================================
# Snowflake
# =============================================================================

@st.cache_data(ttl=600, show_spinner=False)
def load_market() -> pd.DataFrame:
    df = session.sql(
        f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            LISTING_COUNT,
            LISTINGS_WITH_PRICE,
            AVERAGE_PRICE,
            MEDIAN_PRICE
        FROM {MARKET_TABLE}
        WHERE LOWER(SOURCE_COUNTRY) = 'france'
          AND LOWER(SOURCE_CITY) = 'lyon'
        ORDER BY SNAPSHOT_DATE
        """
    ).to_pandas()

    return normalize_dataframe(df)


@st.cache_data(ttl=600, show_spinner=False)
def load_price_distribution() -> pd.DataFrame:
    df = session.sql(
        f"""
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
        FROM {PRICE_DISTRIBUTION_TABLE}
        WHERE LOWER(SOURCE_COUNTRY) = 'france'
          AND LOWER(SOURCE_CITY) = 'lyon'
        ORDER BY
            SNAPSHOT_DATE,
            PRICE_BAND_ORDER
        """
    ).to_pandas()

    return normalize_dataframe(df)


@st.cache_data(ttl=600, show_spinner=False)
def load_price_transitions() -> pd.DataFrame:
    df = session.sql(
        f"""
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
        FROM {PRICE_TRANSITION_TABLE}
        WHERE LOWER(SOURCE_COUNTRY) = 'france'
          AND LOWER(SOURCE_CITY) = 'lyon'
          AND UPPER(TRANSITION_TYPE) = 'CONSECUTIVE'
        ORDER BY SNAPSHOT_DATE
        """
    ).to_pandas()

    return normalize_dataframe(df)

market = load_market()
distribution = load_price_distribution()
transitions = load_price_transitions()

if market.empty:
    st.error("Aucune donnée marché disponible pour Lyon.")
    st.stop()

# =============================================================================
# Global snapshot
# =============================================================================

snapshot_dates = (
    market["snapshot_date"]
    .dropna()
    .drop_duplicates()
    .sort_values()
    .tolist()
)

selected_snapshot = pd.to_datetime(
    render_sidebar(snapshot_dates)
)

current_rows = market[
    market["snapshot_date"] == selected_snapshot
]

if current_rows.empty:
    st.error(
        "Le snapshot sélectionné est absent de MART_MARKET_SNAPSHOT."
    )
    st.stop()

current = current_rows.iloc[0]

listing_count = to_int(current["listing_count"])
listings_with_price = to_int(current["listings_with_price"])

price_coverage = (
    listings_with_price / listing_count * 100
    if listing_count > 0
    else 0.0
)

average_price = current["average_price"]
median_price = current["median_price"]

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

# =============================================================================
# Niveau des prix
# =============================================================================

section_header(
    "Niveau des prix",
    (
        "Situation tarifaire du marché observé "
        f"au {format_date_fr(selected_snapshot)}."
    ),
)

if listings_with_price > 0:
    kpi_grid(
        [
            {
                "label": "Prix médian",
                "value": format_price(median_price),
                "detail": "Parmi les annonces disposant d'un prix",
            },
            {
                "label": "Prix moyen",
                "value": format_price(average_price),
                "detail": "Parmi les annonces disposant d'un prix",
            },
            {
                "label": "Annonces avec prix",
                "value": format_count(listings_with_price),
                "detail": (
                    f"sur {format_count(listing_count)} "
                    "annonces observées"
                ),
            },
            {
                "label": "Couverture tarifaire",
                "value": format_pct(price_coverage),
                "detail": (
                    "Part du marché disposant "
                    "d'un prix exploitable"
                ),
            },
        ],
        columns=2,
    )

    if price_coverage < 100:
        insight_box(
            f"Couverture tarifaire partielle · {format_pct(price_coverage)}",
            (
                "Les statistiques de prix portent sur "
                f"{format_count(listings_with_price)} annonces parmi "
                f"les {format_count(listing_count)} observées. "
                "Elles décrivent donc uniquement la population "
                "disposant d'une information tarifaire."
            ),
        )

else:
    st.warning(
        "Aucune information de prix n'est disponible pour ce snapshot. "
        "L'absence de valeur tarifaire ne doit pas être interprétée "
        "comme un prix de 0 €."
    )

st.divider()

# =============================================================================
# Distribution des prix
# =============================================================================

section_header(
    "Distribution des prix",
    (
        "Répartition des annonces disposant d'un prix exploitable "
        "selon leur tranche tarifaire."
    ),
)

selected_distribution = distribution[
    distribution["snapshot_date"] == selected_snapshot
].copy()

selected_distribution = selected_distribution[
    selected_distribution["price_band"].astype(str).str.upper()
    != "NO_PRICE"
].copy()

selected_distribution = selected_distribution.sort_values(
    "price_band_order"
)

if listings_with_price == 0 or selected_distribution.empty:
    st.info(
        "Aucune distribution tarifaire exploitable "
        "pour cette observation."
    )

else:
    selected_distribution["price_band_label"] = (
        selected_distribution["price_band"]
        .apply(format_price_band)
    )

    selected_distribution["chart_label"] = (
        selected_distribution.apply(
            lambda row: (
                f"{format_integer(row['listing_count'])} · "
                f"{format_percent(row['priced_listing_share_pct'])}"
            ),
            axis=1,
        )
    )

    ordered_bands = selected_distribution[
        "price_band_label"
    ].tolist()

    distribution_chart = (
        alt.Chart(selected_distribution)
        .mark_bar(
            color=CHART_BLUE,
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4,
        )
        .encode(
            x=alt.X(
                "price_band_label:N",
                sort=ordered_bands,
                title=None,
                axis=alt.Axis(
                    labelAngle=0,
                    labelPadding=10,
                ),
            ),
            y=alt.Y(
                "listing_count:Q",
                title="Nombre d'annonces",
            ),
            tooltip=[
                alt.Tooltip(
                    "price_band_label:N",
                    title="Tranche",
                ),
                alt.Tooltip(
                    "listing_count:Q",
                    title="Annonces",
                    format=",.0f",
                ),
                alt.Tooltip(
                    "priced_listing_share_pct:Q",
                    title="Part tarifée",
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
        .properties(height=330)
    )

    distribution_labels = (
        alt.Chart(selected_distribution)
        .mark_text(
            dy=-10,
            fontSize=12,
        )
        .encode(
            x=alt.X(
                "price_band_label:N",
                sort=ordered_bands,
            ),
            y=alt.Y("listing_count:Q"),
            text=alt.Text("chart_label:N"),
        )
    )

    st.altair_chart(
        distribution_chart + distribution_labels,
        use_container_width=True,
    )

    note(
        "Les pourcentages représentent la part de chaque tranche "
        "parmi les annonces disposant d'un prix, et non parmi "
        "l'ensemble des annonces observées."
    )

    section_header(
        "Détail des tranches tarifaires"
    )

    price_table = selected_distribution[
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

    price_table.columns = [
        "Tranche de prix",
        "Annonces",
        "Part tarifée",
        "Prix moyen",
        "Prix médian",
        "Minimum",
        "Maximum",
    ]

    price_table["Annonces"] = (
        price_table["Annonces"]
        .apply(format_integer)
    )

    price_table["Part tarifée"] = (
        price_table["Part tarifée"]
        .apply(format_percent)
    )

    for column in (
        "Prix moyen",
        "Prix médian",
        "Minimum",
        "Maximum",
    ):
        price_table[column] = (
            price_table[column]
            .apply(
                lambda value: format_currency(
                    value,
                    decimals=2,
                )
            )
        )

    st.dataframe(
        price_table,
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# =============================================================================
# Historique des prix
# =============================================================================

section_header(
    "Évolution historique des prix",
    (
        "Évolution du prix moyen et du prix médian "
        "à travers les observations historiques."
    ),
)

history = market.copy().sort_values("snapshot_date")

history["date_label"] = (
    history["snapshot_date"]
    .apply(format_date_fr)
)

history_order = history["date_label"].tolist()

history_prices = history[
    history["listings_with_price"] > 0
].copy()

if not history_prices.empty:
    history_long = history_prices.melt(
        id_vars=[
            "snapshot_date",
            "date_label",
        ],
        value_vars=[
            "average_price",
            "median_price",
        ],
        var_name="metric",
        value_name="price",
    )

    history_long["metric_label"] = (
        history_long["metric"].map(
            {
                "average_price": "Prix moyen",
                "median_price": "Prix médian",
            }
        )
    )

    price_history_chart = (
        alt.Chart(history_long)
        .mark_line(
            point=alt.OverlayMarkDef(
                filled=True,
                size=65,
            ),
            strokeWidth=2.5,
        )
        .encode(
            x=alt.X(
                "date_label:N",
                sort=history_order,
                title="Date d'observation",
                axis=alt.Axis(
                    labelAngle=0,
                    labelPadding=10,
                ),
            ),
            y=alt.Y(
                "price:Q",
                title="Prix (€)",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color(
                "metric_label:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Prix moyen",
                        "Prix médian",
                    ],
                    range=[
                        CHART_BLUE,
                        CHART_LIGHT_BLUE,
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
                    "metric_label:N",
                    title="Indicateur",
                ),
                alt.Tooltip(
                    "price:Q",
                    title="Prix",
                    format=".2f",
                ),
            ],
        )
        .properties(height=300)
    )

    st.altair_chart(
        price_history_chart,
        use_container_width=True,
    )

else:
    st.info(
        "Aucune observation historique ne contient "
        "d'information tarifaire exploitable."
    )


# =============================================================================
# Couverture historique
# =============================================================================

section_header(
    "Couverture tarifaire historique"
)

coverage_history = history.copy()

coverage_history["price_coverage_pct"] = (
    coverage_history["listings_with_price"]
    / coverage_history["listing_count"]
    * 100
)

coverage_history["coverage_label"] = (
    coverage_history["price_coverage_pct"]
    .apply(format_percent)
)

coverage_chart = (
    alt.Chart(coverage_history)
    .mark_bar(
        color=CHART_BLUE,
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
    )
    .encode(
        x=alt.X(
            "date_label:N",
            sort=history_order,
            title="Date d'observation",
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
        tooltip=[
            alt.Tooltip(
                "date_label:N",
                title="Observation",
            ),
            alt.Tooltip(
                "listing_count:Q",
                title="Annonces observées",
                format=",.0f",
            ),
            alt.Tooltip(
                "listings_with_price:Q",
                title="Annonces avec prix",
                format=",.0f",
            ),
            alt.Tooltip(
                "price_coverage_pct:Q",
                title="Couverture",
                format=".1f",
            ),
        ],
    )
    .properties(height=270)
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
            sort=history_order,
        ),
        y=alt.Y("price_coverage_pct:Q"),
        text=alt.Text("coverage_label:N"),
    )
)

st.altair_chart(
    coverage_chart + coverage_labels,
    use_container_width=True,
)

note(
    "Les évolutions de prix doivent être lues conjointement avec "
    "la couverture tarifaire. L'observation du 22/12/2025 ne "
    "contient aucune information de prix : l'absence de valeur "
    "ne correspond donc pas à un prix de 0 €."
)


st.divider()


# =============================================================================
# Evolution à annonces comparables
# =============================================================================

section_header(
    "Évolution à annonces comparables",
    (
        "Analyse des changements tarifaires pour les annonces "
        "disposant d'un prix dans deux observations consécutives."
    ),
)

selected_transition_rows = transitions[
    transitions["snapshot_date"] == selected_snapshot
].copy()

selected_transition_rows = selected_transition_rows[
    selected_transition_rows[
        "transition_type"
    ].astype(str).str.upper()
    == "CONSECUTIVE"
]

if selected_transition_rows.empty:
    st.info(
        "Aucune transition consécutive comparable n'est disponible "
        "pour cette observation. Cela peut notamment correspondre "
        "au premier snapshot historique."
    )

else:
    transition = (
        selected_transition_rows
        .sort_values(
            "previous_snapshot_date",
            ascending=False,
        )
        .iloc[0]
    )

    previous_snapshot = transition[
        "previous_snapshot_date"
    ]

    comparable_count = to_int(
        transition["comparable_listing_count"]
    )

    comparable_coverage = to_float(
        transition["comparable_price_coverage_pct"]
    )

    previous_median = transition[
        "median_previous_price"
    ]

    current_median = transition[
        "median_current_price"
    ]

    median_change = transition[
        "median_price_change"
    ]

    median_change_pct = transition[
        "median_price_change_pct"
    ]

    insight_box(
        (
            f"Du {format_date_fr(previous_snapshot)} "
            f"au {format_date_fr(selected_snapshot)}"
        ),
        (
            "L'analyse porte sur "
            f"{format_count(comparable_count)} annonces "
            "disposant d'un prix exploitable dans les deux "
            "observations consécutives."
        ),
    )

    kpi_grid(
        [
            {
                "label": "Annonces comparables",
                "value": format_count(comparable_count),
                "detail": (
                    "Population disposant d'un prix "
                    "dans les deux observations"
                ),
            },
            {
                "label": "Couverture comparable",
                "value": format_pct(comparable_coverage),
                "detail": "Part des observations de la transition",
            },
            {
                "label": "Prix médian précédent",
                "value": format_price(previous_median),
                "detail": format_date_fr(previous_snapshot),
            },
            {
                "label": "Prix médian actuel",
                "value": format_price(current_median),
                "detail": format_date_fr(selected_snapshot),
            },
        ],
        columns=2,
    )

    # Python 3.11-compatible:
    # calculate the formatted percentage outside the f-string.
    median_change_pct_label = format_signed_percent(
        median_change_pct,
        decimals=1,
        na="N/D",
    )

    transition_grid(
        [
            {
                "label": "Variation médiane",
                "value": format_signed_currency(
                    median_change,
                    decimals=2,
                    na="N/D",
                ),
                "detail": (
                    f"{median_change_pct_label} "
                    "par rapport au prix médian précédent"
                ),
            },
        ],
        columns=2,
    )

    st.write("")

    section_header(
        "Sens des évolutions",
        (
            "Répartition des annonces comparables selon "
            "le sens de leur changement de prix."
        ),
    )

    movement_data = pd.DataFrame(
        {
            "movement": [
                "En hausse",
                "En baisse",
                "Inchangé",
            ],
            "count": [
                to_int(
                    transition[
                        "price_increase_count"
                    ]
                ),
                to_int(
                    transition[
                        "price_decrease_count"
                    ]
                ),
                to_int(
                    transition[
                        "unchanged_price_count"
                    ]
                ),
            ],
            "share": [
                to_float(
                    transition[
                        "price_increase_share_pct"
                    ]
                ),
                to_float(
                    transition[
                        "price_decrease_share_pct"
                    ]
                ),
                to_float(
                    transition[
                        "unchanged_price_share_pct"
                    ]
                ),
            ],
        }
    )

    movement_data["label"] = (
        movement_data.apply(
            lambda row: (
                f"{format_integer(row['count'])} · "
                f"{format_percent(row['share'])}"
            ),
            axis=1,
        )
    )

    movement_order = [
        "En hausse",
        "En baisse",
        "Inchangé",
    ]

    movement_colors = alt.Scale(
        domain=movement_order,
        range=[
            CHART_GREEN,
            CHART_RED,
            CHART_GREY,
        ],
    )

    movement_chart = (
        alt.Chart(movement_data)
        .mark_bar(
            cornerRadiusEnd=4,
        )
        .encode(
            y=alt.Y(
                "movement:N",
                sort=movement_order,
                title=None,
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
                scale=movement_colors,
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
                    format=",.0f",
                ),
                alt.Tooltip(
                    "share:Q",
                    title="Part",
                    format=".1f",
                ),
            ],
        )
        .properties(height=210)
    )

    movement_labels = (
        alt.Chart(movement_data)
        .mark_text(
            align="left",
            dx=8,
            fontSize=12,
        )
        .encode(
            y=alt.Y(
                "movement:N",
                sort=movement_order,
            ),
            x=alt.X("count:Q"),
            text=alt.Text("label:N"),
        )
    )

    st.altair_chart(
        movement_chart + movement_labels,
        use_container_width=True,
    )

    note(
        "Cette analyse neutralise une partie des changements de "
        "population entre snapshots en comparant uniquement les "
        "annonces disposant d'un prix exploitable dans les deux "
        "observations consécutives."
    )


# =============================================================================
# Methodological explanation
# =============================================================================

st.divider()

with st.expander(
    "Comment interpréter les prix ?"
):
    st.markdown(
        """
**Prix du marché**

Le prix moyen et le prix médian sont calculés uniquement sur les
annonces pour lesquelles Inside Airbnb fournit une information
tarifaire exploitable au snapshot considéré.

**Couverture tarifaire**

La couverture correspond à la part des annonces observées disposant
d'un prix. Une variation de prix entre deux snapshots doit donc être
interprétée conjointement avec cette couverture.

**Distribution**

Les parts des tranches tarifaires sont calculées parmi les annonces
disposant d'un prix. La catégorie sans prix n'entre pas dans la
distribution présentée.

**Évolution à annonces comparables**

Cette analyse utilise uniquement les transitions de type
`CONSECUTIVE`. Une annonce doit disposer d'un prix exploitable dans
les deux observations consécutives pour participer à la comparaison.

Les transitions `AFTER_GAP` ne sont volontairement pas utilisées ici,
car elles comparent des observations séparées par un ou plusieurs
snapshots manquants.

**Limite d'interprétation**

Le prix affiché dans les données Inside Airbnb est une information
observée dans la source. Il ne constitue ni un revenu réalisé, ni une
preuve de réservation, ni un prix effectivement payé par un voyageur.
        """
    )