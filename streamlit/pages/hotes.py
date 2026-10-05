
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
from ui.formatters import (
    format_date_fr,
    format_decimal,
    format_integer,
    format_percent,
)
from ui.config import MARTS, get_session
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

HOST_TABLE = (
    f"{MARTS}."
    "MART_HOST_SNAPSHOT"
)

CHART_BLUE = "#356DCC"
CHART_LIGHT_BLUE = "#79B8F3"
CHART_GREEN = "#2E8B57"
CHART_ORANGE = "#E59A3A"
CHART_PURPLE = "#7B61C9"
CHART_GREY = "#8A94A6"

PORTFOLIO_ORDER = [
    "1 annonce",
    "2 à 5",
    "6 à 10",
    "11 à 20",
    "21 et +",
]

CONCENTRATION_ORDER = [
    "Top 1 %",
    "Top 5 %",
    "Top 10 %",
]


# ============================================================
# Helpers
# ============================================================

def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    result = df.copy()
    result.columns = result.columns.str.lower()

    if "snapshot_date" in result.columns:
        result["snapshot_date"] = pd.to_datetime(
            result["snapshot_date"]
        )

    return result


def to_float(value, default=0.0) -> float:
    if value is None or pd.isna(value):
        return default

    return float(value)


def to_int(value, default=0) -> int:
    if value is None or pd.isna(value):
        return default

    return int(value)


def format_count(value) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return format_integer(value)


def format_pct(value, decimals=1) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return format_percent(
        value,
        decimals=decimals,
    )


def format_dec(value, decimals=2) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return format_decimal(
        value,
        decimals=decimals,
    )


# ============================================================
# Snowflake
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def load_hosts() -> pd.DataFrame:
    df = session.sql(
        f"""
        SELECT *
        FROM {HOST_TABLE}
        ORDER BY
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE
        """
    ).to_pandas()

    return normalize_dataframe(df)

hosts = load_hosts()

# ============================================================
# Global context
# ============================================================

(
    selected_country,
    selected_city,
    selected_snapshot,
) = render_sidebar()

selected_snapshot = pd.to_datetime(
    selected_snapshot
)

country_key = str(
    selected_country
).strip().lower()

city_key = str(
    selected_city
).strip().lower()

hosts = hosts.loc[
    hosts["source_country"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq(country_key)
    &
    hosts["source_city"]
    .astype(str)
    .str.strip()
    .str.lower()
    .eq(city_key)
].copy()

city_label = format_location_name(
    selected_city
)

country_label = format_location_name(
    selected_country
)

location_label = (
    f"{city_label}, {country_label}"
)

if hosts.empty:
    st.error(
        "Aucune donnée relative aux hôtes "
        f"n'est disponible pour {location_label}."
    )
    st.stop()

snapshot_dates = (
    hosts["snapshot_date"]
    .dropna()
    .drop_duplicates()
    .sort_values()
    .tolist()
)

current_rows = hosts.loc[
    hosts["snapshot_date"]
    == selected_snapshot
].copy()

if current_rows.empty:
    st.error(
        "Le snapshot sélectionné est absent de "
        "MART_HOST_SNAPSHOT "
        f"pour {location_label}."
    )
    st.stop()

current = current_rows.iloc[0]

# ============================================================
# Header
# ============================================================

page_header(
    title="Hôtes",
    subtitle=(
        "Analyse de la structure des hôtes Airbnb "
        f"à {city_label}, de leurs portefeuilles d'annonces "
        "et de la concentration de l'offre."
    ),
    icon="👥",
    badges=[
        f"📍 {location_label}",
        f"🗓️ {format_date_fr(selected_snapshot)}",
        (
            f"📁 {format_integer(len(snapshot_dates))} "
            "snapshots disponibles"
        ),
    ],
)

# ============================================================
# Market structure
# ============================================================

section_header(
    "Structure des hôtes",
    (
        "Principaux indicateurs décrivant la population d'hôtes "
        f"observée au {format_date_fr(selected_snapshot)}."
    ),
)

kpi_grid(
    [
        {
            "label": "Hôtes observés",
            "value": format_count(
                current["host_count"]
            ),
            "detail": (
                "Nombre d'identifiants d'hôtes distincts "
                "observés"
            ),
        },
        {
            "label": "Annonces par hôte",
            "value": format_dec(
                current["average_listings_per_host"],
                decimals=2,
            ),
            "detail": (
                "Nombre moyen d'annonces observées "
                "par hôte"
            ),
        },
        {
            "label": "Hôtes multi-annonces",
            "value": format_pct(
                current["multi_listing_host_share_pct"]
            ),
            "detail": (
                "Part des hôtes contrôlant "
                "au moins deux annonces"
            ),
        },
        {
            "label": "Superhosts",
            "value": format_pct(
                current["superhost_share_pct"]
            ),
            "detail": (
                "Part des hôtes identifiés "
                "comme Superhosts"
            ),
        },
    ],
    columns=2,
)

insight_box(
    "Une offre majoritairement portée par des mono-annonces",
    (
        f"{format_pct(current['single_listing_host_share_pct'])} "
        "des hôtes observés ne disposent que d'une annonce, contre "
        f"{format_pct(current['multi_listing_host_share_pct'])} "
        "disposant d'au moins deux annonces."
    ),
)


st.divider()


# ============================================================
# Portfolio structure
# ============================================================

section_header(
    "Structure des portefeuilles",
    (
        "Répartition des hôtes selon le nombre d'annonces "
        "qu'ils contrôlent dans le snapshot sélectionné."
    ),
)

portfolio = pd.DataFrame(
    {
        "portfolio": PORTFOLIO_ORDER,
        "hosts": [
            to_int(
                current["single_listing_host_count"]
            ),
            to_int(
                current["host_count_2_to_5"]
            ),
            to_int(
                current["host_count_6_to_10"]
            ),
            to_int(
                current["host_count_11_to_20"]
            ),
            to_int(
                current["host_count_21_plus"]
            ),
        ],
    }
)

portfolio["label"] = (
    portfolio["hosts"]
    .apply(format_integer)
)

portfolio_chart = (
    alt.Chart(portfolio)
    .mark_bar(
        color=CHART_BLUE,
        cornerRadiusTopRight=4,
        cornerRadiusBottomRight=4,
    )
    .encode(
        y=alt.Y(
            "portfolio:N",
            sort=PORTFOLIO_ORDER,
            title=None,
            axis=alt.Axis(
                labelPadding=10,
            ),
        ),
        x=alt.X(
            "hosts:Q",
            title="Nombre d'hôtes",
        ),
        tooltip=[
            alt.Tooltip(
                "portfolio:N",
                title="Portefeuille",
            ),
            alt.Tooltip(
                "hosts:Q",
                title="Hôtes",
                format=",.0f",
            ),
        ],
    )
    .properties(height=260)
)

portfolio_labels = (
    alt.Chart(portfolio)
    .mark_text(
        align="left",
        baseline="middle",
        dx=8,
        fontSize=12,
    )
    .encode(
        y=alt.Y(
            "portfolio:N",
            sort=PORTFOLIO_ORDER,
        ),
        x=alt.X("hosts:Q"),
        text=alt.Text("label:N"),
    )
)

st.altair_chart(
    portfolio_chart + portfolio_labels,
    use_container_width=True,
)

note(
    "Les catégories décrivent le nombre d'annonces observées "
    "pour un même identifiant d'hôte au snapshot sélectionné."
)


# ============================================================
# Single vs multi-listing hosts
# ============================================================

section_header(
    "Mono-annonces vs multi-annonces",
    (
        "Comparaison entre la structure de la population d'hôtes "
        "et la part de l'offre qu'ils contrôlent."
    ),
)

single_host_count = to_int(
    current["single_listing_host_count"]
)

multi_host_count = to_int(
    current["multi_listing_host_count"]
)

single_listing_count = to_int(
    current[
        "listings_controlled_by_single_listing_hosts"
    ]
)

multi_listing_count = to_int(
    current[
        "listings_controlled_by_multi_listing_hosts"
    ]
)

kpi_grid(
    [
        {
            "label": "Hôtes mono-annonce",
            "value": format_count(single_host_count),
            "detail": (
                f"{format_pct(current['single_listing_host_share_pct'])} "
                "des hôtes observés"
            ),
        },
        {
            "label": "Hôtes multi-annonces",
            "value": format_count(multi_host_count),
            "detail": (
                f"{format_pct(current['multi_listing_host_share_pct'])} "
                "des hôtes observés"
            ),
        },
        {
            "label": "Annonces des mono-annonces",
            "value": format_count(single_listing_count),
            "detail": (
                f"{format_pct(current['single_listing_host_listing_share_pct'])} "
                "des annonces observées"
            ),
        },
        {
            "label": "Annonces des multi-annonces",
            "value": format_count(multi_listing_count),
            "detail": (
                f"{format_pct(current['multi_listing_host_listing_share_pct'])} "
                "des annonces observées"
            ),
        },
    ],
    columns=2,
)

insight_box(
    "Population d'hôtes et contrôle de l'offre",
    (
        f"Les hôtes multi-annonces représentent "
        f"{format_pct(current['multi_listing_host_share_pct'])} "
        "des hôtes mais contrôlent "
        f"{format_pct(current['multi_listing_host_listing_share_pct'])} "
        "des annonces observées."
    ),
)


st.divider()


# ============================================================
# Concentration
# ============================================================

section_header(
    "Concentration de l'offre",
    (
        "Part des annonces contrôlées par les groupes d'hôtes "
        "disposant des portefeuilles les plus importants."
    ),
)

concentration = pd.DataFrame(
    {
        "group": CONCENTRATION_ORDER,
        "share": [
            to_float(
                current["top_1_pct_listing_share_pct"]
            ),
            to_float(
                current["top_5_pct_listing_share_pct"]
            ),
            to_float(
                current["top_10_pct_listing_share_pct"]
            ),
        ],
    }
)

concentration["label"] = (
    concentration["share"]
    .apply(
        lambda value: format_percent(
            value,
            decimals=1,
        )
    )
)

concentration_chart = (
    alt.Chart(concentration)
    .mark_bar(
        color=CHART_BLUE,
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
        size=70,
    )
    .encode(
        x=alt.X(
            "group:N",
            sort=CONCENTRATION_ORDER,
            title=None,
            axis=alt.Axis(
                labelAngle=0,
                labelPadding=10,
            ),
        ),
        y=alt.Y(
            "share:Q",
            title="Part des annonces (%)",
            scale=alt.Scale(
                domain=[0, 100],
            ),
        ),
        tooltip=[
            alt.Tooltip(
                "group:N",
                title="Groupe",
            ),
            alt.Tooltip(
                "share:Q",
                title="Part des annonces",
                format=".2f",
            ),
        ],
    )
    .properties(height=300)
)

concentration_labels = (
    alt.Chart(concentration)
    .mark_text(
        dy=-10,
        fontSize=12,
    )
    .encode(
        x=alt.X(
            "group:N",
            sort=CONCENTRATION_ORDER,
        ),
        y=alt.Y("share:Q"),
        text=alt.Text("label:N"),
    )
)

st.altair_chart(
    concentration_chart + concentration_labels,
    use_container_width=True,
)

kpi_grid(
    [
        {
            "label": "HHI",
            "value": format_dec(
                current["host_hhi"],
                decimals=2,
            ),
            "detail": (
                "Indice synthétique de concentration "
                "utilisé pour comparer les snapshots"
            ),
        },
    ],
    columns=1,
)

note(
    "Les indicateurs Top 1 %, Top 5 % et Top 10 % sont cumulatifs : "
    "le Top 1 % est inclus dans le Top 5 %, lui-même inclus dans "
    "le Top 10 %."
)

st.divider()

# ============================================================
# Host profile
# ============================================================

section_header(
    "Profil des hôtes",
    (
        "Caractéristiques complémentaires de la population "
        "d'hôtes observée."
    ),
)

kpi_grid(
    [
        {
            "label": "Superhosts",
            "value": format_count(
                current["superhost_count"]
            ),
            "detail": (
                f"{format_pct(current['superhost_share_pct'])} "
                "des hôtes observés"
            ),
        },
        {
            "label": "Identité vérifiée",
            "value": format_count(
                current["identity_verified_host_count"]
            ),
            "detail": (
                f"{format_pct(current['identity_verified_host_share_pct'])} "
                "des hôtes observés"
            ),
        },
        {
            "label": "Portefeuille médian",
            "value": format_dec(
                current["median_listings_per_host"],
                decimals=0,
            ),
            "detail": (
                "Nombre médian d'annonces observées "
                "par hôte"
            ),
        },
        {
            "label": "Plus grand portefeuille",
            "value": format_count(
                current["max_listings_per_host"]
            ),
            "detail": (
                "Nombre maximal d'annonces observées "
                "pour un même hôte"
            ),
        },
    ],
    columns=2,
)


st.divider()


# ============================================================
# Historical hosts / listings
# ============================================================

section_header(
    "Évolution historique des hôtes",
    (
        "Évolution du nombre d'hôtes et d'annonces "
        "à travers les observations historiques."
    ),
)

host_history = hosts[
    [
        "snapshot_date",
        "host_count",
        "listing_count",
    ]
].copy()

host_history = host_history.sort_values(
    "snapshot_date"
)

host_history["date_label"] = (
    host_history["snapshot_date"]
    .apply(format_date_fr)
)

history_order = (
    host_history["date_label"]
    .tolist()
)

host_history_long = host_history.melt(
    id_vars=[
        "snapshot_date",
        "date_label",
    ],
    value_vars=[
        "host_count",
        "listing_count",
    ],
    var_name="metric",
    value_name="count",
)

host_history_long["metric_label"] = (
    host_history_long["metric"].map(
        {
            "host_count": "Hôtes",
            "listing_count": "Annonces",
        }
    )
)

host_history_chart = (
    alt.Chart(host_history_long)
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
            "count:Q",
            title="Nombre",
            scale=alt.Scale(
                zero=False,
            ),
        ),
        color=alt.Color(
            "metric_label:N",
            title=None,
            scale=alt.Scale(
                domain=[
                    "Hôtes",
                    "Annonces",
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
                "count:Q",
                title="Nombre",
                format=",.0f",
            ),
        ],
    )
    .properties(height=310)
)

st.altair_chart(
    host_history_chart,
    use_container_width=True,
)

note(
    "Les variations entre snapshots peuvent refléter à la fois "
    "des évolutions du marché observé et des différences de "
    "population présente dans les extractions Inside Airbnb."
)


# ============================================================
# Multi-listing evolution
# ============================================================

section_header(
    "Évolution des hôtes multi-annonces",
    (
        "Comparaison historique entre leur poids dans la population "
        "d'hôtes et leur poids dans l'offre observée."
    ),
)

multi_history = hosts[
    [
        "snapshot_date",
        "multi_listing_host_share_pct",
        "multi_listing_host_listing_share_pct",
    ]
].copy()

multi_history = multi_history.sort_values(
    "snapshot_date"
)

multi_history["date_label"] = (
    multi_history["snapshot_date"]
    .apply(format_date_fr)
)

multi_history_long = multi_history.melt(
    id_vars=[
        "snapshot_date",
        "date_label",
    ],
    value_vars=[
        "multi_listing_host_share_pct",
        "multi_listing_host_listing_share_pct",
    ],
    var_name="metric",
    value_name="share",
)

multi_history_long["metric_label"] = (
    multi_history_long["metric"].map(
        {
            "multi_listing_host_share_pct":
                "Hôtes multi-annonces",
            "multi_listing_host_listing_share_pct":
                "Annonces contrôlées",
        }
    )
)

multi_chart = (
    alt.Chart(multi_history_long)
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
            "share:Q",
            title="Part (%)",
            scale=alt.Scale(
                domain=[0, 100],
            ),
        ),
        color=alt.Color(
            "metric_label:N",
            title=None,
            scale=alt.Scale(
                domain=[
                    "Hôtes multi-annonces",
                    "Annonces contrôlées",
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
                "share:Q",
                title="Part",
                format=".1f",
            ),
        ],
    )
    .properties(height=300)
)

st.altair_chart(
    multi_chart,
    use_container_width=True,
)


# ============================================================
# Concentration evolution
# ============================================================

section_header(
    "Évolution de la concentration",
    (
        "Évolution de la part des annonces contrôlées "
        "par les principaux groupes d'hôtes."
    ),
)

concentration_history = hosts[
    [
        "snapshot_date",
        "top_1_pct_listing_share_pct",
        "top_5_pct_listing_share_pct",
        "top_10_pct_listing_share_pct",
    ]
].copy()

concentration_history = (
    concentration_history
    .sort_values("snapshot_date")
)

concentration_history["date_label"] = (
    concentration_history["snapshot_date"]
    .apply(format_date_fr)
)

concentration_history_long = (
    concentration_history.melt(
        id_vars=[
            "snapshot_date",
            "date_label",
        ],
        value_vars=[
            "top_1_pct_listing_share_pct",
            "top_5_pct_listing_share_pct",
            "top_10_pct_listing_share_pct",
        ],
        var_name="metric",
        value_name="share",
    )
)

concentration_history_long["metric_label"] = (
    concentration_history_long["metric"].map(
        {
            "top_1_pct_listing_share_pct": "Top 1 %",
            "top_5_pct_listing_share_pct": "Top 5 %",
            "top_10_pct_listing_share_pct": "Top 10 %",
        }
    )
)

concentration_history_chart = (
    alt.Chart(concentration_history_long)
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
            "share:Q",
            title="Part des annonces (%)",
            scale=alt.Scale(
                domain=[0, 100],
            ),
        ),
        color=alt.Color(
            "metric_label:N",
            title=None,
            sort=CONCENTRATION_ORDER,
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
                title="Groupe",
            ),
            alt.Tooltip(
                "share:Q",
                title="Part des annonces",
                format=".2f",
            ),
        ],
    )
    .properties(height=300)
)

st.altair_chart(
    concentration_history_chart,
    use_container_width=True,
)


# ============================================================
# Historical table
# ============================================================

section_header(
    "Indicateurs historiques",
    (
        "Vue détaillée des principaux indicateurs "
        "pour chaque observation."
    ),
)

history_table = hosts[
    [
        "snapshot_date",
        "host_count",
        "listing_count",
        "average_listings_per_host",
        "single_listing_host_share_pct",
        "multi_listing_host_share_pct",
        "multi_listing_host_listing_share_pct",
        "superhost_share_pct",
        "top_1_pct_listing_share_pct",
        "top_5_pct_listing_share_pct",
        "top_10_pct_listing_share_pct",
        "host_hhi",
    ]
].copy()

history_table["snapshot_date"] = (
    history_table["snapshot_date"]
    .apply(format_date_fr)
)

history_table = history_table.rename(
    columns={
        "snapshot_date": "Date",
        "host_count": "Hôtes",
        "listing_count": "Annonces",
        "average_listings_per_host": "Annonces / hôte",
        "single_listing_host_share_pct": "Hôtes mono (%)",
        "multi_listing_host_share_pct": "Hôtes multi (%)",
        "multi_listing_host_listing_share_pct":
            "Annonces des multi (%)",
        "superhost_share_pct": "Superhosts (%)",
        "top_1_pct_listing_share_pct": "Top 1 %",
        "top_5_pct_listing_share_pct": "Top 5 %",
        "top_10_pct_listing_share_pct": "Top 10 %",
        "host_hhi": "HHI",
    }
)

st.dataframe(
    history_table,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Hôtes": st.column_config.NumberColumn(
            format="localized",
        ),
        "Annonces": st.column_config.NumberColumn(
            format="localized",
        ),
        "Annonces / hôte":
            st.column_config.NumberColumn(
                format="%.2f",
            ),
        "Hôtes mono (%)":
            st.column_config.NumberColumn(
                format="%.1f %%",
            ),
        "Hôtes multi (%)":
            st.column_config.NumberColumn(
                format="%.1f %%",
            ),
        "Annonces des multi (%)":
            st.column_config.NumberColumn(
                format="%.1f %%",
            ),
        "Superhosts (%)":
            st.column_config.NumberColumn(
                format="%.1f %%",
            ),
        "Top 1 %":
            st.column_config.NumberColumn(
                format="%.2f %%",
            ),
        "Top 5 %":
            st.column_config.NumberColumn(
                format="%.2f %%",
            ),
        "Top 10 %":
            st.column_config.NumberColumn(
                format="%.2f %%",
            ),
        "HHI":
            st.column_config.NumberColumn(
                format="%.2f",
            ),
    },
)


# ============================================================
# Methodology
# ============================================================

st.divider()

with st.expander(
    "Comment interpréter les indicateurs d'hôtes ?"
):
    st.markdown(
        """
**Hôte mono-annonce**

Un hôte mono-annonce contrôle une seule annonce observée dans le
snapshot sélectionné.

**Hôte multi-annonces**

Un hôte multi-annonces contrôle au moins deux annonces observées.
La part de ces hôtes peut être comparée à la part des annonces
qu'ils contrôlent afin d'étudier la structure de l'offre.

**Structure des portefeuilles**

Les catégories de portefeuille sont déterminées à partir du nombre
d'annonces observées pour chaque identifiant d'hôte au snapshot
considéré. Elles ne constituent pas une qualification juridique ou
professionnelle de l'hôte.

**Top 1 %, Top 5 % et Top 10 %**

Ces indicateurs mesurent la part des annonces contrôlées par les
groupes d'hôtes disposant des portefeuilles les plus importants.
Les groupes sont cumulatifs : le Top 1 % est inclus dans le Top 5 %,
lui-même inclus dans le Top 10 %.

**HHI**

L'indicateur HHI synthétise la concentration de la distribution des
annonces entre les hôtes. Dans cette application, il est principalement
utilisé pour comparer la concentration entre les différentes dates
d'observation.

**Superhost et identité vérifiée**

Ces attributs proviennent des informations disponibles dans les
snapshots Inside Airbnb. Ils décrivent l'état observé au moment de
l'extraction.

**Évolution historique**

Les évolutions entre snapshots décrivent les populations observées à
chaque date. Elles peuvent donc refléter à la fois une évolution du
marché et des changements dans la population présente dans les
extractions.

**Limite d'interprétation**

Les indicateurs décrivent les identifiants d'hôtes présents dans les
données Inside Airbnb. Ils ne permettent pas, à eux seuls, d'identifier
juridiquement les personnes ou organisations qui exploitent les
annonces.
        """
    )