import altair as alt
import pandas as pd
import streamlit as st

from ui.config import MARTS, get_session
from ui.sidebar import render_sidebar

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
    format_date_short_fr,
    format_integer,
    format_percent,
    format_signed_integer,
    safe_ratio,
)

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
def load_data():

    market = session.sql(f"""
        SELECT *
        FROM {MARTS}.MART_MARKET_SNAPSHOT
        ORDER BY SNAPSHOT_DATE
    """).to_pandas()

    availability = session.sql(f"""
        SELECT *
        FROM {MARTS}.MART_AVAILABILITY_HORIZON_SNAPSHOT
        ORDER BY SNAPSHOT_DATE
    """).to_pandas()

    hosts = session.sql(f"""
        SELECT *
        FROM {MARTS}.MART_HOST_SNAPSHOT
        ORDER BY SNAPSHOT_DATE
    """).to_pandas()

    transitions = session.sql(f"""
        SELECT *
        FROM {MARTS}.MART_MARKET_TRANSITION
        ORDER BY SNAPSHOT_DATE
    """).to_pandas()

    for dataframe in [
        market,
        availability,
        hosts,
        transitions,
    ]:
        dataframe.columns = dataframe.columns.str.lower()

    return market, availability, hosts, transitions

market, availability, hosts, transitions = load_data()

# ============================================================
# Data preparation
# ============================================================

for dataframe in [
    market,
    availability,
    hosts,
    transitions,
]:
    dataframe["snapshot_date"] = pd.to_datetime(
        dataframe["snapshot_date"]
    ).dt.date


snapshot_dates = market["snapshot_date"].tolist()

# ============================================================
# Sidebar
# ============================================================

selected_snapshot = render_sidebar(
    snapshot_dates=snapshot_dates,
)

selected_snapshot = pd.to_datetime(
    selected_snapshot
).date()

# ============================================================
# Selected snapshot
# ============================================================

current_market = market[
    market["snapshot_date"] == selected_snapshot
].iloc[0]

current_availability = availability[
    availability["snapshot_date"] == selected_snapshot
].iloc[0]

current_hosts = hosts[
    hosts["snapshot_date"] == selected_snapshot
].iloc[0]

current_transition_df = transitions[
    transitions["snapshot_date"] == selected_snapshot
]

current_transition = (
    current_transition_df.iloc[0]
    if not current_transition_df.empty
    else None
)

# ============================================================
# Derived indicators
# ============================================================

entire_home_share = safe_ratio(
    current_market["entire_home_listing_count"],
    current_market["listing_count"],
)

price_coverage = safe_ratio(
    current_market["listings_with_price"],
    current_market["listing_count"],
)

listings_per_host = (
    float(current_market["listing_count"])
    / float(current_hosts["host_count"])
    if float(current_hosts["host_count"]) > 0
    else None
)

# ============================================================
# Header
# ============================================================

page_header(
    title="Inside Airbnb Analytics",
    icon="🏙️",
    subtitle=(
        "Observatoire du marché de la location courte durée à Lyon"
    ),
    badges=[
        "🇫🇷 Lyon, France",
        f"📅 {format_date_short_fr(selected_snapshot)}",
        f"🗂️ {format_integer(len(snapshot_dates))} observations historiques",
    ],
)

# ============================================================
# Main KPIs
# ============================================================

section_header(
    "Marché en un coup d'œil",
    "Principaux indicateurs pour l'observation sélectionnée.",
)

kpi_grid(
    [
        {
            "label": "Annonces observées",
            "value": format_integer(
                current_market["listing_count"]
            ),
            "detail": "Population du marché observé",
        },
        {
            "label": "Prix médian",
            "value": format_currency(
                current_market["median_price"]
            ),
            "detail": (
                f"Couverture tarifaire : "
                f"{format_percent(price_coverage)}"
            ),
        },
        {
            "label": "Disponibilité à 30 jours",
            "value": format_percent(
                current_availability[
                    "market_availability_rate_30d_pct"
                ]
            ),
            "detail": "Part des jours déclarés disponibles",
        },
        {
            "label": "Hôtes observés",
            "value": format_integer(
                current_hosts["host_count"]
            ),
            "detail": (
                f"{listings_per_host:.2f} annonce par hôte"
                if listings_per_host is not None
                else "N/D"
            ).replace(".", ","),
        },
    ]
)

# ============================================================
# Market dynamics
# ============================================================

st.divider()

section_header(
    "Dynamique du marché",
    "Décomposition de l'évolution depuis l'observation précédente.",
)

if current_transition is None:

    st.info(
        "Il s'agit de la première observation disponible. "
        "Aucune transition antérieure ne peut être calculée."
    )

else:

    previous_snapshot = pd.to_datetime(
        current_transition["previous_snapshot_date"]
    ).date()

    net_change = current_transition[
        "net_listing_change"
    ]

    returned_count = current_transition[
        "returned_after_gap_listing_count"
    ]

    newly_observed_count = current_transition[
        "newly_observed_listing_count"
    ]

    insight_box(
        (
            f"Variation nette : "
            f"{format_signed_integer(net_change)} annonces"
        ),
        (
            f"Entre le {format_date_fr(previous_snapshot)} "
            f"et le {format_date_fr(selected_snapshot)}, "
            f"le marché observé évolue de "
            f"{format_signed_integer(net_change)} annonces. "
            f"{format_integer(returned_count)} annonces sont "
            f"des retours après absence, contre "
            f"{format_integer(newly_observed_count)} annonces "
            f"nouvellement observées."
        ),
    )

    transition_grid(
    [
        {
            "label": "Conservées",
            "value": format_integer(
                current_transition[
                    "retained_listing_count"
                ]
            ),
            "detail": (
                f"{format_percent(current_transition['retention_rate_pct'])} "
                "des annonces précédentes"
            ),
        },
        {
            "label": "Nouvellement observées",
            "value": format_integer(
                current_transition[
                    "newly_observed_listing_count"
                ]
            ),
            "detail": "Première apparition dans l'historique",
        },
        {
            "label": "Retours après absence",
            "value": format_integer(
                current_transition[
                    "returned_after_gap_listing_count"
                ]
            ),
            "detail": "Déjà observées historiquement",
        },
        {
            "label": "Disparues",
            "value": format_integer(
                current_transition[
                    "disappeared_listing_count"
                ]
            ),
            "detail": (
                f"{format_percent(current_transition['disappearance_rate_pct'])} "
                "des annonces précédentes"
            ),
        },
    ]
)

# ============================================================
# Market structure
# ============================================================

st.divider()

section_header(
    "Structure du marché",
    "Composition de l'offre et caractéristiques des hôtes.",
)

kpi_grid(
    [
        {
            "label": "Logements entiers",
            "value": format_percent(entire_home_share),
            "detail": (
                f"{format_integer(current_market['entire_home_listing_count'])} "
                "annonces"
            ),
        },
        {
            "label": "Hôtes multi-annonces",
            "value": format_percent(
                current_hosts[
                    "multi_listing_host_share_pct"
                ]
            ),
            "detail": (
                "Part des hôtes contrôlant plusieurs annonces"
            ),
        },
        {
            "label": "Superhosts",
            "value": format_percent(
                current_hosts["superhost_share_pct"]
            ),
            "detail": "Part des hôtes observés",
        },
        {
            "label": "Couverture tarifaire",
            "value": format_percent(price_coverage),
            "detail": (
                f"{format_integer(current_market['listings_with_price'])} "
                "annonces avec prix"
            ),
        },
    ]
)

# ============================================================
# Historical evolution
# ============================================================

st.divider()

section_header(
    "Évolution historique",
    "Nombre d'annonces observées à chaque snapshot disponible.",
)

chart_data = market[
    [
        "snapshot_date",
        "listing_count",
    ]
].copy()

chart_data["snapshot_date"] = pd.to_datetime(
    chart_data["snapshot_date"]
)

chart_data["date_label"] = chart_data[
    "snapshot_date"
].apply(format_date_fr)

chart_data["listing_label"] = chart_data[
    "listing_count"
].apply(format_integer)

snapshot_order = chart_data[
    "date_label"
].tolist()

line = (
    alt.Chart(chart_data)
    .mark_line(
        point={
            "filled": True,
            "size": 85,
        },
        strokeWidth=3,
    )
    .encode(
        x=alt.X(
            "date_label:N",
            title=None,
            sort=snapshot_order,
            axis=alt.Axis(
                labelAngle=0,
                grid=False,
                labelPadding=10,
            ),
        ),
        y=alt.Y(
            "listing_count:Q",
            title="Nombre d'annonces",
            scale=alt.Scale(
                zero=False,
                padding=25,
            ),
            axis=alt.Axis(
                format=",d",
                grid=True,
                gridOpacity=0.15,
            ),
        ),
        tooltip=[
            alt.Tooltip(
                "date_label:N",
                title="Observation",
            ),
            alt.Tooltip(
                "listing_label:N",
                title="Annonces",
            ),
        ],
    )
)

labels = (
    alt.Chart(chart_data)
    .mark_text(
        dy=-14,
        fontSize=12,
        fontWeight=600,
    )
    .encode(
        x=alt.X(
            "date_label:N",
            sort=snapshot_order,
        ),
        y="listing_count:Q",
        text="listing_label:N",
    )
)

historical_chart = (
    line + labels
).properties(
    height=320,
).configure_view(
    strokeWidth=0,
)

st.altair_chart(
    historical_chart,
    use_container_width=True,
)

# ============================================================
# Availability
# ============================================================

st.divider()

section_header(
    "Disponibilité future",
    (
        "Part des jours déclarés disponibles à différents "
        "horizons après l'observation."
    ),
)

kpi_grid(
    [
        {
            "label": "30 jours",
            "value": format_percent(
                current_availability[
                    "market_availability_rate_30d_pct"
                ]
            ),
            "detail": "Horizon court terme",
        },
        {
            "label": "60 jours",
            "value": format_percent(
                current_availability[
                    "market_availability_rate_60d_pct"
                ]
            ),
            "detail": "Horizon intermédiaire",
        },
        {
            "label": "90 jours",
            "value": format_percent(
                current_availability[
                    "market_availability_rate_90d_pct"
                ]
            ),
            "detail": "Horizon trimestriel",
        },
        {
            "label": "365 jours",
            "value": format_percent(
                current_availability[
                    "market_availability_rate_365d_pct"
                ]
            ),
            "detail": "Horizon annuel",
        },
    ]
)

note(
    "La disponibilité correspond aux jours marqués disponibles "
    "dans le calendrier Inside Airbnb. Elle ne constitue pas "
    "une mesure d'occupation réelle."
)

# ============================================================
# Interpretation
# ============================================================

st.divider()

section_header(
    "À retenir",
    "Points de vigilance pour interpréter correctement les indicateurs.",
)

if price_coverage is not None and price_coverage < 80:

    insight_box(
        "Couverture tarifaire partielle",
        (
            f"Un prix est disponible pour "
            f"{format_percent(price_coverage)} des annonces "
            f"du snapshot sélectionné. Les indicateurs de prix "
            f"doivent être interprétés sur cette population."
        ),
    )

elif price_coverage is not None:

    insight_box(
        "Bonne couverture tarifaire",
        (
            f"Un prix est disponible pour "
            f"{format_percent(price_coverage)} des annonces "
            f"du snapshot sélectionné."
        ),
    )

note(
    "Une variation entre deux snapshots ne correspond pas "
    "nécessairement à des créations ou suppressions d'annonces. "
    "Pour les définitions détaillées et les limites des données, "
    "consultez la page Méthodologie."
)