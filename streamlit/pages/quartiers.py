import altair as alt
import pandas as pd
import streamlit as st

from ui.components import (
    insight_box,
    kpi_grid,
    note,
    page_header,
    section_header,
)
from ui.config import MARTS, get_session
from ui.formatters import (
    format_currency,
    format_date_fr,
    format_integer,
    format_percent,
)
from ui.sidebar import format_location_name, render_sidebar
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
# Configuration
# ============================================================

NEIGHBOURHOOD_SNAPSHOT_TABLE = (
    f"{MARTS}.MART_NEIGHBOURHOOD_SNAPSHOT"
)

NEIGHBOURHOOD_TRANSITION_TABLE = (
    f"{MARTS}.MART_NEIGHBOURHOOD_TRANSITION"
)

CHART_BLUE = "#356DCC"
CHART_LIGHT_BLUE = "#79B8F3"
CHART_GREEN = "#2E8B57"
CHART_RED = "#D95C5C"
CHART_GREY = "#8A94A6"


# ============================================================
# Helpers
# ============================================================

def normalize_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize Snowflake column names and date columns."""

    if dataframe.empty:
        return dataframe

    result = dataframe.copy()
    result.columns = result.columns.str.lower()

    for column in (
        "snapshot_date",
        "previous_snapshot_date",
    ):
        if column in result.columns:
            result[column] = pd.to_datetime(
                result[column]
            )

    return result


def safe_divide(
    numerator,
    denominator,
    multiplier=1.0,
):
    """Return a safe division result."""

    if (
        denominator is None
        or pd.isna(denominator)
        or denominator == 0
    ):
        return 0.0

    if numerator is None or pd.isna(numerator):
        return 0.0

    return (
        float(numerator)
        / float(denominator)
        * multiplier
    )


def format_optional_currency(value):
    """Format an optional monetary value."""

    if value is None or pd.isna(value):
        return "N/D"

    return format_currency(value)


def format_optional_percent(value):
    """Format an optional percentage value."""

    if value is None or pd.isna(value):
        return "N/D"

    return format_percent(value)


def format_neighbourhood(value):
    """Return a readable neighbourhood label."""

    if value is None or pd.isna(value):
        return "Non renseigné"

    value = str(value).strip()

    if not value:
        return "Non renseigné"

    return value


# ============================================================
# Data loading
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_neighbourhood_data():
    """Load neighbourhood snapshots and transitions."""

    snapshots = session.sql(
        f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            NEIGHBOURHOOD,

            LISTING_COUNT,
            ENTIRE_HOME_LISTING_COUNT,
            PRIVATE_ROOM_LISTING_COUNT,
            SHARED_ROOM_LISTING_COUNT,

            HOST_COUNT,
            SUPERHOST_LISTING_COUNT,

            LISTINGS_WITH_PRICE,
            AVERAGE_PRICE,
            MEDIAN_PRICE,

            AVERAGE_AVAILABILITY_RATE_PCT,
            AVERAGE_AVAILABILITY_30,
            AVERAGE_AVAILABILITY_365,

            NATIVE_REVIEW_COUNT_TOTAL,
            RECONSTRUCTED_REVIEW_COUNT_TOTAL,
            RECONSTRUCTED_REVIEW_COUNT_L30D,
            RECONSTRUCTED_REVIEW_COUNT_L90D,
            RECONSTRUCTED_REVIEW_COUNT_L365D,

            AVERAGE_LISTING_LATITUDE,
            AVERAGE_LISTING_LONGITUDE

        FROM {NEIGHBOURHOOD_SNAPSHOT_TABLE}

        ORDER BY
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            LISTING_COUNT DESC,
            NEIGHBOURHOOD
        """
    ).to_pandas()

    transitions = session.sql(
        f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            NEIGHBOURHOOD,

            PREVIOUS_SNAPSHOT_DATE,
            SNAPSHOT_DATE,
            DAYS_BETWEEN_SNAPSHOTS,

            PREVIOUS_LISTING_COUNT,
            CURRENT_LISTING_COUNT,

            NET_LISTING_CHANGE,
            NET_LISTING_CHANGE_PCT,

            RETAINED_LISTING_COUNT,
            DISAPPEARED_LISTING_COUNT,

            MOVED_OUT_LISTING_COUNT,
            MOVED_IN_LISTING_COUNT,

            NEWLY_OBSERVED_LISTING_COUNT,
            RETURNED_AFTER_GAP_LISTING_COUNT,

            RETENTION_RATE_PCT,
            DISAPPEARANCE_RATE_PCT,
            MOVED_OUT_RATE_PCT,

            NEWLY_OBSERVED_SHARE_PCT,
            RETURNED_AFTER_GAP_SHARE_PCT,
            MOVED_IN_SHARE_PCT,

            HAS_RETURNED_LISTINGS,
            HAS_GEOGRAPHIC_MOVEMENT

        FROM {NEIGHBOURHOOD_TRANSITION_TABLE}

        ORDER BY
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            NEIGHBOURHOOD
        """
    ).to_pandas()

    return (
        normalize_dataframe(snapshots),
        normalize_dataframe(transitions),
    )


snapshots, transitions = load_neighbourhood_data()


# ============================================================
# Geographic context
# ============================================================

(
    selected_country,
    selected_city,
    selected_snapshot,
) = render_sidebar()

selected_snapshot = pd.Timestamp(
    selected_snapshot
)


# ============================================================
# Geographic filtering
# ============================================================

snapshots = snapshots[
    (
        snapshots["source_country"]
        == selected_country
    )
    & (
        snapshots["source_city"]
        == selected_city
    )
].copy()

transitions = transitions[
    (
        transitions["source_country"]
        == selected_country
    )
    & (
        transitions["source_city"]
        == selected_city
    )
].copy()


if snapshots.empty:
    st.error(
        "Aucune donnée par quartier n'est disponible "
        "pour la localisation sélectionnée."
    )
    st.stop()


snapshot_dates = sorted(
    snapshots["snapshot_date"]
    .dropna()
    .unique()
    .tolist()
)


# ============================================================
# Selected observation
# ============================================================

current = snapshots[
    snapshots["snapshot_date"]
    == selected_snapshot
].copy()


if current.empty:
    st.error(
        "Aucune donnée par quartier n'est disponible "
        "pour l'observation sélectionnée."
    )
    st.stop()


current["neighbourhood_label"] = (
    current["neighbourhood"]
    .apply(format_neighbourhood)
)

current = current.sort_values(
    [
        "listing_count",
        "neighbourhood_label",
    ],
    ascending=[False, True],
).reset_index(drop=True)


# ============================================================
# Derived indicators
# ============================================================

neighbourhood_count = int(
    current["neighbourhood"]
    .nunique()
)

total_listings = int(
    current["listing_count"].sum()
)

total_hosts = int(
    current["host_count"].sum()
)

total_priced_listings = int(
    current["listings_with_price"].sum()
)


current["market_share_pct"] = (
    current["listing_count"]
    .apply(
        lambda value: safe_divide(
            value,
            total_listings,
            multiplier=100.0,
        )
    )
)


current["entire_home_share_pct"] = (
    current.apply(
        lambda row: safe_divide(
            row["entire_home_listing_count"],
            row["listing_count"],
            multiplier=100.0,
        ),
        axis=1,
    )
)


current["private_room_share_pct"] = (
    current.apply(
        lambda row: safe_divide(
            row["private_room_listing_count"],
            row["listing_count"],
            multiplier=100.0,
        ),
        axis=1,
    )
)


current["shared_room_share_pct"] = (
    current.apply(
        lambda row: safe_divide(
            row["shared_room_listing_count"],
            row["listing_count"],
            multiplier=100.0,
        ),
        axis=1,
    )
)


current["superhost_listing_share_pct"] = (
    current.apply(
        lambda row: safe_divide(
            row["superhost_listing_count"],
            row["listing_count"],
            multiplier=100.0,
        ),
        axis=1,
    )
)


current["price_coverage_pct"] = (
    current.apply(
        lambda row: safe_divide(
            row["listings_with_price"],
            row["listing_count"],
            multiplier=100.0,
        ),
        axis=1,
    )
)


largest_neighbourhood = current.iloc[0]

largest_neighbourhood_name = (
    largest_neighbourhood[
        "neighbourhood_label"
    ]
)

largest_neighbourhood_listings = int(
    largest_neighbourhood["listing_count"]
)

largest_neighbourhood_share = float(
    largest_neighbourhood[
        "market_share_pct"
    ]
)


# ============================================================
# Header
# ============================================================

page_header(
    title="Quartiers",
    subtitle=(
        "Lecture territoriale de l'offre Airbnb à "
        f"{format_location_name(selected_city)} : "
        "volume, structure, prix, disponibilité "
        "et évolution des quartiers."
    ),
    icon="🏘️",
    badges=[
        (
            f"📍 {format_location_name(selected_city)}, "
            f"{format_location_name(selected_country)}"
        ),
        (
            f"🗓️ "
            f"{format_date_fr(selected_snapshot)}"
        ),
        (
            f"📁 "
            f"{format_integer(len(snapshot_dates))} "
            "observations historiques"
        ),
    ],
)


# ============================================================
# Market structure
# ============================================================

section_header(
    "Structure territoriale",
    (
        "Répartition de l'offre entre les quartiers "
        f"au {format_date_fr(selected_snapshot)}."
    ),
)


kpi_grid(
    [
        {
            "label": "Quartiers observés",
            "value": format_integer(
                neighbourhood_count
            ),
            "detail": (
                "Territoires représentés "
                "dans cette observation"
            ),
        },
        {
            "label": "Annonces observées",
            "value": format_integer(
                total_listings
            ),
            "detail": (
                "Somme des annonces "
                "des quartiers observés"
            ),
        },
        {
            "label": "Quartier principal",
            "value": largest_neighbourhood_name,
            "detail": (
                f"{format_integer(largest_neighbourhood_listings)} "
                "annonces"
            ),
        },
        {
            "label": "Poids du quartier principal",
            "value": format_percent(
                largest_neighbourhood_share
            ),
            "detail": (
                "Part des annonces de "
                f"{largest_neighbourhood_name}"
            ),
        },
    ],
    columns=2,
)


insight_box(
    (
        f"Concentration territoriale · "
        f"{largest_neighbourhood_name}"
    ),
    (
        f"Le quartier le plus représenté concentre "
        f"{format_integer(largest_neighbourhood_listings)} "
        f"annonces, soit "
        f"{format_percent(largest_neighbourhood_share)} "
        f"des {format_integer(total_listings)} annonces "
        "observées pour cette localisation."
    ),
)


# ============================================================
# Supply distribution
# ============================================================

st.divider()

section_header(
    "Répartition de l'offre",
    (
        "Nombre d'annonces et poids de chaque quartier "
        "dans le marché observé."
    ),
)


supply_chart_data = current[
    [
        "neighbourhood_label",
        "listing_count",
        "market_share_pct",
    ]
].copy()


supply_chart_data["listing_label"] = (
    supply_chart_data["listing_count"]
    .apply(format_integer)
)


neighbourhood_order = (
    supply_chart_data[
        "neighbourhood_label"
    ].tolist()
)


supply_bars = (
    alt.Chart(supply_chart_data)
    .mark_bar(
        color=CHART_BLUE,
        cornerRadiusEnd=4,
    )
    .encode(
        y=alt.Y(
            "neighbourhood_label:N",
            title=None,
            sort=neighbourhood_order,
            axis=alt.Axis(
                labelLimit=260,
                labelPadding=8,
            ),
        ),
        x=alt.X(
            "listing_count:Q",
            title="Nombre d'annonces",
        ),
        tooltip=[
            alt.Tooltip(
                "neighbourhood_label:N",
                title="Quartier",
            ),
            alt.Tooltip(
                "listing_count:Q",
                title="Annonces",
                format=",d",
            ),
            alt.Tooltip(
                "market_share_pct:Q",
                title="Part du marché (%)",
                format=".1f",
            ),
        ],
    )
    .properties(
        height=max(
            300,
            neighbourhood_count * 32,
        )
    )
)


supply_labels = (
    alt.Chart(supply_chart_data)
    .mark_text(
        align="left",
        baseline="middle",
        dx=8,
        fontSize=11,
    )
    .encode(
        y=alt.Y(
            "neighbourhood_label:N",
            sort=neighbourhood_order,
        ),
        x=alt.X(
            "listing_count:Q",
        ),
        text=alt.Text(
            "listing_label:N",
        ),
    )
)


st.altair_chart(
    supply_bars + supply_labels,
    use_container_width=True,
)


# ============================================================
# Price analysis
# ============================================================

st.divider()

section_header(
    "Prix par quartier",
    (
        "Comparaison des niveaux tarifaires parmi "
        "les annonces disposant d'un prix exploitable."
    ),
)


price_data = current[
    (
        current["listings_with_price"] > 0
    )
    & current["median_price"].notna()
].copy()


if price_data.empty:

    st.info(
        "Aucune information tarifaire exploitable "
        "n'est disponible pour cette observation."
    )

else:

    price_data = price_data.sort_values(
        [
            "median_price",
            "listing_count",
        ],
        ascending=[False, False],
    )

    price_data["median_price_label"] = (
        price_data["median_price"]
        .apply(format_optional_currency)
    )

    price_order = (
        price_data[
            "neighbourhood_label"
        ].tolist()
    )

    price_bars = (
        alt.Chart(price_data)
        .mark_bar(
            color=CHART_LIGHT_BLUE,
            cornerRadiusEnd=4,
        )
        .encode(
            y=alt.Y(
                "neighbourhood_label:N",
                title=None,
                sort=price_order,
                axis=alt.Axis(
                    labelLimit=260,
                    labelPadding=8,
                ),
            ),
            x=alt.X(
                "median_price:Q",
                title="Prix médian (€)",
                scale=alt.Scale(
                    zero=True,
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "neighbourhood_label:N",
                    title="Quartier",
                ),
                alt.Tooltip(
                    "median_price:Q",
                    title="Prix médian",
                    format=".2f",
                ),
                alt.Tooltip(
                    "average_price:Q",
                    title="Prix moyen",
                    format=".2f",
                ),
                alt.Tooltip(
                    "listings_with_price:Q",
                    title="Annonces avec prix",
                    format=",d",
                ),
                alt.Tooltip(
                    "price_coverage_pct:Q",
                    title="Couverture tarifaire (%)",
                    format=".1f",
                ),
            ],
        )
        .properties(
            height=max(
                300,
                len(price_data) * 32,
            )
        )
    )

    price_labels = (
        alt.Chart(price_data)
        .mark_text(
            align="left",
            baseline="middle",
            dx=8,
            fontSize=11,
        )
        .encode(
            y=alt.Y(
                "neighbourhood_label:N",
                sort=price_order,
            ),
            x=alt.X(
                "median_price:Q",
            ),
            text=alt.Text(
                "median_price_label:N",
            ),
        )
    )

    st.altair_chart(
        price_bars + price_labels,
        use_container_width=True,
    )

    note(
        "Les prix moyen et médian sont calculés uniquement "
        "sur les annonces disposant d'une information "
        "tarifaire exploitable. La couverture tarifaire "
        "peut varier selon le quartier."
    )


# ============================================================
# Room type structure
# ============================================================

st.divider()

section_header(
    "Structure de l'offre",
    (
        "Composition de l'offre par type de logement "
        "dans chaque quartier."
    ),
)


room_type_data = current[
    [
        "neighbourhood_label",
        "entire_home_listing_count",
        "private_room_listing_count",
        "shared_room_listing_count",
    ]
].copy()


room_type_data = room_type_data.rename(
    columns={
        "entire_home_listing_count": (
            "Logement entier"
        ),
        "private_room_listing_count": (
            "Chambre privée"
        ),
        "shared_room_listing_count": (
            "Chambre partagée"
        ),
    }
)


room_type_long = room_type_data.melt(
    id_vars=[
        "neighbourhood_label",
    ],
    var_name="room_type",
    value_name="listing_count",
)


room_type_chart = (
    alt.Chart(room_type_long)
    .mark_bar()
    .encode(
        y=alt.Y(
            "neighbourhood_label:N",
            title=None,
            sort=neighbourhood_order,
            axis=alt.Axis(
                labelLimit=260,
                labelPadding=8,
            ),
        ),
        x=alt.X(
            "listing_count:Q",
            title="Nombre d'annonces",
            stack="zero",
        ),
        color=alt.Color(
            "room_type:N",
            title=None,
            scale=alt.Scale(
                domain=[
                    "Logement entier",
                    "Chambre privée",
                    "Chambre partagée",
                ],
                range=[
                    CHART_BLUE,
                    CHART_LIGHT_BLUE,
                    CHART_GREY,
                ],
            ),
            legend=alt.Legend(
                orient="bottom",
                direction="horizontal",
            ),
        ),
        tooltip=[
            alt.Tooltip(
                "neighbourhood_label:N",
                title="Quartier",
            ),
            alt.Tooltip(
                "room_type:N",
                title="Type",
            ),
            alt.Tooltip(
                "listing_count:Q",
                title="Annonces",
                format=",d",
            ),
        ],
    )
    .properties(
        height=max(
            300,
            neighbourhood_count * 32,
        )
    )
)


st.altair_chart(
    room_type_chart,
    use_container_width=True,
)


# ============================================================
# Availability
# ============================================================

st.divider()

section_header(
    "Disponibilité publique par quartier",
    (
        "Comparaison de la disponibilité moyenne "
        "publiquement observée dans les calendriers Airbnb."
    ),
)


availability_data = current[
    [
        "neighbourhood_label",
        "listing_count",
        "average_availability_rate_pct",
        "average_availability_30",
        "average_availability_365",
    ]
].copy()


availability_data = availability_data[
    availability_data[
        "average_availability_rate_pct"
    ].notna()
].copy()


if availability_data.empty:

    st.info(
        "Aucune donnée de disponibilité exploitable "
        "n'est disponible pour cette observation."
    )

else:

    availability_data = (
        availability_data.sort_values(
            "average_availability_rate_pct",
            ascending=False,
        )
    )

    availability_order = (
        availability_data[
            "neighbourhood_label"
        ].tolist()
    )

    availability_chart = (
        alt.Chart(availability_data)
        .mark_bar(
            color=CHART_GREEN,
            cornerRadiusEnd=4,
        )
        .encode(
            y=alt.Y(
                "neighbourhood_label:N",
                title=None,
                sort=availability_order,
                axis=alt.Axis(
                    labelLimit=260,
                    labelPadding=8,
                ),
            ),
            x=alt.X(
                "average_availability_rate_pct:Q",
                title="Disponibilité moyenne (%)",
                scale=alt.Scale(
                    domain=[0, 100],
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "neighbourhood_label:N",
                    title="Quartier",
                ),
                alt.Tooltip(
                    "listing_count:Q",
                    title="Annonces",
                    format=",d",
                ),
                alt.Tooltip(
                    "average_availability_rate_pct:Q",
                    title="Disponibilité moyenne (%)",
                    format=".1f",
                ),
                alt.Tooltip(
                    "average_availability_30:Q",
                    title="Jours disponibles à 30 jours",
                    format=".1f",
                ),
                alt.Tooltip(
                    "average_availability_365:Q",
                    title="Jours disponibles à 365 jours",
                    format=".1f",
                ),
            ],
        )
        .properties(
            height=max(
                300,
                len(availability_data) * 32,
            )
        )
    )

    st.altair_chart(
        availability_chart,
        use_container_width=True,
    )


note(
    "La disponibilité correspond aux jours publiquement "
    "observés comme disponibles sur Airbnb. Elle ne doit "
    "pas être interprétée comme un taux d'inoccupation "
    "observé ni comme l'inverse d'un taux d'occupation."
)


# ============================================================
# Review activity
# ============================================================

st.divider()

section_header(
    "Activité récente",
    (
        "Volume de reviews reconstruit à partir des données "
        "de reviews disponibles jusqu'au snapshot."
    ),
)


review_data = current[
    [
        "neighbourhood_label",
        "reconstructed_review_count_l30d",
        "reconstructed_review_count_l90d",
        "reconstructed_review_count_l365d",
    ]
].copy()


review_data = review_data.sort_values(
    "reconstructed_review_count_l90d",
    ascending=False,
)


review_order = (
    review_data[
        "neighbourhood_label"
    ].tolist()
)


review_chart = (
    alt.Chart(review_data)
    .mark_bar(
        color=CHART_BLUE,
        cornerRadiusEnd=4,
    )
    .encode(
        y=alt.Y(
            "neighbourhood_label:N",
            title=None,
            sort=review_order,
            axis=alt.Axis(
                labelLimit=260,
                labelPadding=8,
            ),
        ),
        x=alt.X(
            "reconstructed_review_count_l90d:Q",
            title="Reviews reconstruites sur 90 jours",
        ),
        tooltip=[
            alt.Tooltip(
                "neighbourhood_label:N",
                title="Quartier",
            ),
            alt.Tooltip(
                "reconstructed_review_count_l30d:Q",
                title="Reviews L30D",
                format=",d",
            ),
            alt.Tooltip(
                "reconstructed_review_count_l90d:Q",
                title="Reviews L90D",
                format=",d",
            ),
            alt.Tooltip(
                "reconstructed_review_count_l365d:Q",
                title="Reviews L365D",
                format=",d",
            ),
        ],
    )
    .properties(
        height=max(
            300,
            neighbourhood_count * 32,
        )
    )
)


st.altair_chart(
    review_chart,
    use_container_width=True,
)


note(
    "Le volume de reviews est un indicateur d'activité "
    "observable. Il ne constitue pas une mesure directe "
    "du nombre de séjours ni du taux d'occupation."
)


# ============================================================
# Neighbourhood transitions
# ============================================================

st.divider()

section_header(
    "Évolution des quartiers",
    (
        "Variation de l'offre entre l'observation sélectionnée "
        "et l'observation précédente."
    ),
)


current_transition = transitions[
    transitions["snapshot_date"]
    == selected_snapshot
].copy()


if current_transition.empty:

    insight_box(
        "Aucune transition disponible",
        (
            "Cette observation ne dispose pas d'une "
            "comparaison territoriale exploitable avec "
            "une observation précédente."
        ),
    )

else:

    current_transition = (
        current_transition.sort_values(
            [
                "net_listing_change",
                "current_listing_count",
            ],
            ascending=[False, False],
        )
        .reset_index(drop=True)
    )

    current_transition[
        "neighbourhood_label"
    ] = (
        current_transition["neighbourhood"]
        .apply(format_neighbourhood)
    )

    previous_snapshot = (
        current_transition[
            "previous_snapshot_date"
        ]
        .dropna()
        .max()
    )

    total_previous = int(
        current_transition[
            "previous_listing_count"
        ].sum()
    )

    total_current = int(
        current_transition[
            "current_listing_count"
        ].sum()
    )

    total_net_change = int(
        current_transition[
            "net_listing_change"
        ].sum()
    )

    total_retained = int(
        current_transition[
            "retained_listing_count"
        ].sum()
    )

    total_disappeared = int(
        current_transition[
            "disappeared_listing_count"
        ].sum()
    )

    total_new = int(
        current_transition[
            "newly_observed_listing_count"
        ].sum()
    )

    total_returned = int(
        current_transition[
            "returned_after_gap_listing_count"
        ].sum()
    )

    total_moved_in = int(
        current_transition[
            "moved_in_listing_count"
        ].sum()
    )

    total_moved_out = int(
        current_transition[
            "moved_out_listing_count"
        ].sum()
    )

    market_net_change_pct = safe_divide(
        total_net_change,
        total_previous,
        multiplier=100.0,
    )

    retention_pct = safe_divide(
        total_retained,
        total_previous,
        multiplier=100.0,
    )

    disappearance_pct = safe_divide(
        total_disappeared,
        total_previous,
        multiplier=100.0,
    )

    insight_box(
        (
            f"Du "
            f"{format_date_fr(previous_snapshot)} "
            f"au "
            f"{format_date_fr(selected_snapshot)}"
        ),
        (
            f"L'offre territoriale passe de "
            f"{format_integer(total_previous)} à "
            f"{format_integer(total_current)} annonces, "
            f"soit une variation nette de "
            f"{format_integer(total_net_change)} annonces "
            f"({format_percent(market_net_change_pct)})."
        ),
    )

    kpi_grid(
        [
            {
                "label": "Annonces retenues",
                "value": format_integer(
                    total_retained
                ),
                "detail": (
                    f"{format_percent(retention_pct)} "
                    "de la population précédente"
                ),
            },
            {
                "label": "Annonces disparues",
                "value": format_integer(
                    total_disappeared
                ),
                "detail": (
                    f"{format_percent(disappearance_pct)} "
                    "de la population précédente"
                ),
            },
            {
                "label": "Nouvelles observations",
                "value": format_integer(
                    total_new
                ),
                "detail": (
                    "Annonces observées pour "
                    "la première fois"
                ),
            },
            {
                "label": "Retours après absence",
                "value": format_integer(
                    total_returned
                ),
                "detail": (
                    "Annonces réobservées après "
                    "au moins un snapshot absent"
                ),
            },
        ],
        columns=2,
    )

    st.write("")

    section_header(
        "Variation nette par quartier",
        (
            "Écart entre le nombre d'annonces du snapshot "
            "précédent et celui du snapshot sélectionné."
        ),
    )

    transition_chart_data = (
        current_transition[
            [
                "neighbourhood_label",
                "previous_listing_count",
                "current_listing_count",
                "net_listing_change",
                "net_listing_change_pct",
            ]
        ]
        .copy()
    )

    transition_chart_data["direction"] = (
        transition_chart_data[
            "net_listing_change"
        ].apply(
            lambda value: (
                "Hausse"
                if value > 0
                else (
                    "Baisse"
                    if value < 0
                    else "Stable"
                )
            )
        )
    )

    transition_chart_data[
        "change_label"
    ] = (
        transition_chart_data[
            "net_listing_change"
        ].apply(
            lambda value: (
                f"+{format_integer(value)}"
                if value > 0
                else format_integer(value)
            )
        )
    )

    transition_order = (
        transition_chart_data.sort_values(
            "net_listing_change",
            ascending=False,
        )[
            "neighbourhood_label"
        ]
        .tolist()
    )

    transition_bars = (
        alt.Chart(
            transition_chart_data
        )
        .mark_bar(
            cornerRadiusEnd=4,
        )
        .encode(
            y=alt.Y(
                "neighbourhood_label:N",
                title=None,
                sort=transition_order,
                axis=alt.Axis(
                    labelLimit=260,
                    labelPadding=8,
                ),
            ),
            x=alt.X(
                "net_listing_change:Q",
                title="Variation nette des annonces",
            ),
            color=alt.Color(
                "direction:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Hausse",
                        "Baisse",
                        "Stable",
                    ],
                    range=[
                        CHART_GREEN,
                        CHART_RED,
                        CHART_GREY,
                    ],
                ),
                legend=alt.Legend(
                    orient="bottom",
                    direction="horizontal",
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "neighbourhood_label:N",
                    title="Quartier",
                ),
                alt.Tooltip(
                    "previous_listing_count:Q",
                    title="Annonces précédentes",
                    format=",d",
                ),
                alt.Tooltip(
                    "current_listing_count:Q",
                    title="Annonces actuelles",
                    format=",d",
                ),
                alt.Tooltip(
                    "net_listing_change:Q",
                    title="Variation nette",
                    format="+,d",
                ),
                alt.Tooltip(
                    "net_listing_change_pct:Q",
                    title="Variation (%)",
                    format="+.1f",
                ),
            ],
        )
        .properties(
            height=max(
                300,
                len(
                    transition_chart_data
                ) * 32,
            )
        )
    )

    st.altair_chart(
        transition_bars,
        use_container_width=True,
    )

    st.write("")

    section_header(
        "Mouvements territoriaux",
        (
            "Entrées et sorties observables entre quartiers "
            "sur deux snapshots consécutifs."
        ),
    )

    movement_summary = pd.DataFrame(
        {
            "movement": [
                "Entrées dans un quartier",
                "Sorties d'un quartier",
            ],
            "listing_count": [
                total_moved_in,
                total_moved_out,
            ],
        }
    )

    movement_chart = (
        alt.Chart(movement_summary)
        .mark_bar(
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4,
        )
        .encode(
            x=alt.X(
                "movement:N",
                title=None,
                axis=alt.Axis(
                    labelAngle=0,
                ),
            ),
            y=alt.Y(
                "listing_count:Q",
                title="Nombre d'annonces",
            ),
            color=alt.Color(
                "movement:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Entrées dans un quartier",
                        "Sorties d'un quartier",
                    ],
                    range=[
                        CHART_GREEN,
                        CHART_RED,
                    ],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip(
                    "movement:N",
                    title="Mouvement",
                ),
                alt.Tooltip(
                    "listing_count:Q",
                    title="Annonces",
                    format=",d",
                ),
            ],
        )
        .properties(
            height=260,
        )
    )

    st.altair_chart(
        movement_chart,
        use_container_width=True,
    )

    note(
        "Un changement de quartier est directement observable "
        "uniquement lorsqu'une annonce est présente dans deux "
        "snapshots consécutifs et que son quartier change. "
        "Une annonce réapparue après une absence reste classée "
        "comme retour après gap, car son éventuel déplacement "
        "pendant la période non observée ne peut pas être daté."
    )


# ============================================================
# Detailed table
# ============================================================

st.divider()

section_header(
    "Détail des quartiers",
    (
        "Vue synthétique des principaux indicateurs "
        "de l'observation sélectionnée."
    ),
)


detail = current[
    [
        "neighbourhood_label",
        "listing_count",
        "market_share_pct",
        "host_count",
        "entire_home_share_pct",
        "superhost_listing_share_pct",
        "median_price",
        "price_coverage_pct",
        "average_availability_rate_pct",
        "reconstructed_review_count_l90d",
    ]
].copy()


detail = detail.rename(
    columns={
        "neighbourhood_label": "Quartier",
        "listing_count": "Annonces",
        "market_share_pct": "Part du marché",
        "host_count": "Hôtes",
        "entire_home_share_pct": "Logements entiers",
        "superhost_listing_share_pct": (
            "Annonces Superhost"
        ),
        "median_price": "Prix médian",
        "price_coverage_pct": (
            "Couverture tarifaire"
        ),
        "average_availability_rate_pct": (
            "Disponibilité moyenne"
        ),
        "reconstructed_review_count_l90d": (
            "Reviews L90D"
        ),
    }
)


detail["Annonces"] = (
    detail["Annonces"]
    .apply(format_integer)
)

detail["Hôtes"] = (
    detail["Hôtes"]
    .apply(format_integer)
)

detail["Part du marché"] = (
    detail["Part du marché"]
    .apply(format_percent)
)

detail["Logements entiers"] = (
    detail["Logements entiers"]
    .apply(format_percent)
)

detail["Annonces Superhost"] = (
    detail["Annonces Superhost"]
    .apply(format_percent)
)

detail["Prix médian"] = (
    detail["Prix médian"]
    .apply(format_optional_currency)
)

detail["Couverture tarifaire"] = (
    detail["Couverture tarifaire"]
    .apply(format_percent)
)

detail["Disponibilité moyenne"] = (
    detail["Disponibilité moyenne"]
    .apply(format_optional_percent)
)

detail["Reviews L90D"] = (
    detail["Reviews L90D"]
    .apply(format_integer)
)


st.dataframe(
    detail,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Quartier": st.column_config.TextColumn(
            width="large",
        ),
    },
)


# ============================================================
# Methodological note
# ============================================================

st.write("")

with st.expander(
    "Comment interpréter l'analyse par quartier ?"
):

    st.markdown(
        """
**Quartier**

Le découpage territorial correspond à la valeur `neighbourhood`
fournie dans les données préparées à partir d'Inside Airbnb.
Sa nature peut varier selon la localisation étudiée : il ne faut
donc pas supposer qu'il s'agit systématiquement d'un arrondissement
administratif.

**Prix**

Les indicateurs tarifaires sont calculés uniquement sur les annonces
disposant d'un prix exploitable. La couverture tarifaire doit être
prise en compte lors de la comparaison entre quartiers.

**Disponibilité**

La disponibilité correspond aux jours publiquement observés comme
disponibles dans les calendriers Airbnb. Elle ne constitue pas une
mesure directe de vacance ou d'occupation.

**Reviews**

Les volumes récents de reviews sont reconstruits à partir des données
de reviews disponibles jusqu'à la date du snapshot. Ils constituent
un indicateur d'activité observable, et non un nombre direct de
séjours.

**Transitions**

Une disparition signifie qu'une annonce observée au snapshot
précédent n'est plus observée au snapshot courant. Cela ne démontre
pas une sortie permanente d'Airbnb.

Les mouvements géographiques ne sont directement observables que
pour les annonces présentes dans deux snapshots consécutifs.
Une annonce réobservée après une période d'absence est identifiée
comme un retour après gap.
        """
    )