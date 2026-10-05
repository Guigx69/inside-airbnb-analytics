
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
    format_integer,
    format_month_fr,
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
# Configuration
# ============================================================

HORIZON_TABLE = (
    f"{MARTS}."
    "MART_AVAILABILITY_HORIZON_SNAPSHOT"
)

MONTHLY_TABLE = (
    f"{MARTS}."
    "MART_CALENDAR_MONTH_SNAPSHOT"
)

CHART_BLUE = "#356DCC"
CHART_LIGHT_BLUE = "#79B8F3"

HORIZON_ORDER = [
    "30 jours",
    "60 jours",
    "90 jours",
    "365 jours",
]


# ============================================================
# Helpers
# ============================================================

def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize Snowflake column names."""

    if df.empty:
        return df

    result = df.copy()
    result.columns = result.columns.str.lower()

    if "snapshot_date" in result.columns:
        result["snapshot_date"] = pd.to_datetime(
            result["snapshot_date"]
        )

    if "calendar_month" in result.columns:
        result["calendar_month"] = pd.to_datetime(
            result["calendar_month"]
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


def format_pct(value, decimals=1) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return format_percent(
        value,
        decimals=decimals,
    )


def format_count(value) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return format_integer(value)


# ============================================================
# Snowflake
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def load_horizon() -> pd.DataFrame:
    df = session.sql(
        f"""
        SELECT *
        FROM {HORIZON_TABLE}
        WHERE LOWER(SOURCE_COUNTRY) = 'france'
          AND LOWER(SOURCE_CITY) = 'lyon'
        ORDER BY SNAPSHOT_DATE
        """
    ).to_pandas()

    return normalize_dataframe(df)


@st.cache_data(ttl=600, show_spinner=False)
def load_monthly() -> pd.DataFrame:
    df = session.sql(
        f"""
        SELECT *
        FROM {MONTHLY_TABLE}
        WHERE LOWER(SOURCE_COUNTRY) = 'france'
          AND LOWER(SOURCE_CITY) = 'lyon'
        ORDER BY
            SNAPSHOT_DATE,
            CALENDAR_MONTH
        """
    ).to_pandas()

    return normalize_dataframe(df)


horizon = load_horizon()
monthly = load_monthly()


if horizon.empty:
    st.error(
        "Aucune donnée de disponibilité disponible pour Lyon."
    )
    st.stop()


# ============================================================
# Global snapshot
# ============================================================

snapshot_dates = (
    horizon["snapshot_date"]
    .dropna()
    .drop_duplicates()
    .sort_values()
    .tolist()
)

selected_snapshot = pd.to_datetime(
    render_sidebar(snapshot_dates)
)

current_rows = horizon[
    horizon["snapshot_date"] == selected_snapshot
]

if current_rows.empty:
    st.error(
        "Le snapshot sélectionné est absent de "
        "MART_AVAILABILITY_HORIZON_SNAPSHOT."
    )
    st.stop()

current = current_rows.iloc[0]


# ============================================================
# Header
# ============================================================

page_header(
    title="Disponibilité",
    subtitle=(
        "Analyse de la disponibilité déclarée des annonces Airbnb "
        "à Lyon et de la saisonnalité du calendrier futur."
    ),
    icon="🗓️",
    badges=[
        "🇫🇷 Lyon, France",
        f"🗓️ {format_date_fr(selected_snapshot)}",
        (
            f"📁 {format_integer(len(snapshot_dates))} "
            "observations historiques"
        ),
    ],
)


# ============================================================
# Situation actuelle
# ============================================================

section_header(
    "Disponibilité du marché",
    (
        "Part des journées futures marquées comme disponibles "
        f"au {format_date_fr(selected_snapshot)}, selon différents "
        "horizons."
    ),
)

availability_30 = current[
    "market_availability_rate_30d_pct"
]

availability_60 = current[
    "market_availability_rate_60d_pct"
]

availability_90 = current[
    "market_availability_rate_90d_pct"
]

availability_365 = current[
    "market_availability_rate_365d_pct"
]

kpi_grid(
    [
        {
            "label": "Disponibilité à 30 jours",
            "value": format_pct(availability_30),
            "detail": (
                "Part des journées disponibles "
                "sur l'horizon à 30 jours"
            ),
        },
        {
            "label": "Disponibilité à 60 jours",
            "value": format_pct(availability_60),
            "detail": (
                "Part des journées disponibles "
                "sur l'horizon à 60 jours"
            ),
        },
        {
            "label": "Disponibilité à 90 jours",
            "value": format_pct(availability_90),
            "detail": (
                "Part des journées disponibles "
                "sur l'horizon à 90 jours"
            ),
        },
        {
            "label": "Disponibilité à 365 jours",
            "value": format_pct(availability_365),
            "detail": (
                "Part des journées disponibles "
                "sur l'horizon annuel"
            ),
        },
    ],
    columns=2,
)

insight_box(
    "Disponibilité déclarée, pas occupation",
    (
        "Une journée indisponible dans le calendrier Inside Airbnb "
        "ne signifie pas nécessairement qu'elle a été réservée. "
        "Ces indicateurs décrivent l'état du calendrier futur visible "
        "au moment de l'observation et non un taux d'occupation réalisé."
    ),
)


st.divider()


# ============================================================
# Marché vs annonce médiane
# ============================================================

section_header(
    "Marché vs annonce médiane",
    (
        "Comparaison entre la disponibilité agrégée du marché "
        "et celle de l'annonce médiane."
    ),
)

comparison = pd.DataFrame(
    {
        "Horizon": HORIZON_ORDER,
        "Marché": [
            current["market_availability_rate_30d_pct"],
            current["market_availability_rate_60d_pct"],
            current["market_availability_rate_90d_pct"],
            current["market_availability_rate_365d_pct"],
        ],
        "Annonce médiane": [
            current["median_listing_availability_rate_30d_pct"],
            current["median_listing_availability_rate_60d_pct"],
            current["median_listing_availability_rate_90d_pct"],
            current["median_listing_availability_rate_365d_pct"],
        ],
    }
)

comparison_long = comparison.melt(
    id_vars=["Horizon"],
    value_vars=[
        "Marché",
        "Annonce médiane",
    ],
    var_name="Indicateur",
    value_name="Disponibilité",
)

comparison_long["label"] = (
    comparison_long["Disponibilité"]
    .apply(lambda value: format_percent(value, decimals=1))
)

comparison_chart = (
    alt.Chart(comparison_long)
    .mark_bar(
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
        size=38,
    )
    .encode(
        x=alt.X(
            "Horizon:N",
            sort=HORIZON_ORDER,
            title=None,
            axis=alt.Axis(
                labelAngle=0,
                labelPadding=10,
            ),
        ),
        xOffset=alt.XOffset(
            "Indicateur:N",
            sort=[
                "Marché",
                "Annonce médiane",
            ],
        ),
        y=alt.Y(
            "Disponibilité:Q",
            title="Disponibilité (%)",
            scale=alt.Scale(
                domain=[0, 100],
            ),
        ),
        color=alt.Color(
            "Indicateur:N",
            title=None,
            scale=alt.Scale(
                domain=[
                    "Marché",
                    "Annonce médiane",
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
                "Horizon:N",
                title="Horizon",
            ),
            alt.Tooltip(
                "Indicateur:N",
                title="Indicateur",
            ),
            alt.Tooltip(
                "Disponibilité:Q",
                title="Disponibilité",
                format=".1f",
            ),
        ],
    )
    .properties(height=320)
)

comparison_labels = (
    alt.Chart(comparison_long)
    .mark_text(
        dy=-10,
        fontSize=12,
    )
    .encode(
        x=alt.X(
            "Horizon:N",
            sort=HORIZON_ORDER,
        ),
        xOffset=alt.XOffset(
            "Indicateur:N",
            sort=[
                "Marché",
                "Annonce médiane",
            ],
        ),
        y=alt.Y("Disponibilité:Q"),
        text=alt.Text("label:N"),
        color=alt.value("#4B5563"),
    )
)

st.altair_chart(
    comparison_chart + comparison_labels,
    use_container_width=True,
)

note(
    "Le taux du marché rapporte l'ensemble des journées disponibles "
    "à l'ensemble des journées représentées. L'annonce médiane est "
    "calculée à partir du taux propre à chaque annonce et décrit "
    "davantage le comportement d'une annonce typique."
)

st.divider()

# ============================================================
# Horizon detail
# ============================================================

section_header(
    "Détail des horizons",
    (
        "Volumes représentés et indicateurs de disponibilité "
        "pour chaque profondeur de calendrier."
    ),
)

horizon_detail = pd.DataFrame(
    {
        "Horizon": HORIZON_ORDER,
        "Jours représentés": [
            current["represented_days_30d"],
            current["represented_days_60d"],
            current["represented_days_90d"],
            current["represented_days_365d"],
        ],
        "Jours disponibles": [
            current["available_days_30d"],
            current["available_days_60d"],
            current["available_days_90d"],
            current["available_days_365d"],
        ],
        "Disponibilité marché": [
            current[
                "market_availability_rate_30d_pct"
            ],
            current[
                "market_availability_rate_60d_pct"
            ],
            current[
                "market_availability_rate_90d_pct"
            ],
            current[
                "market_availability_rate_365d_pct"
            ],
        ],
        "Disponibilité moyenne": [
            current[
                "average_listing_availability_rate_30d_pct"
            ],
            current[
                "average_listing_availability_rate_60d_pct"
            ],
            current[
                "average_listing_availability_rate_90d_pct"
            ],
            current[
                "average_listing_availability_rate_365d_pct"
            ],
        ],
        "Disponibilité médiane": [
            current[
                "median_listing_availability_rate_30d_pct"
            ],
            current[
                "median_listing_availability_rate_60d_pct"
            ],
            current[
                "median_listing_availability_rate_90d_pct"
            ],
            current[
                "median_listing_availability_rate_365d_pct"
            ],
        ],
    }
)

for column in (
    "Disponibilité marché",
    "Disponibilité moyenne",
    "Disponibilité médiane",
):
    horizon_detail[column] = (
        horizon_detail[column]
        .apply(format_percent)
    )

st.dataframe(
    horizon_detail,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Jours représentés": st.column_config.NumberColumn(
            format="localized",
        ),
        "Jours disponibles": st.column_config.NumberColumn(
            format="localized",
        ),
    },
)

st.divider()

# ============================================================
# Historical availability
# ============================================================

section_header(
    "Évolution historique de la disponibilité",
    (
        "Évolution de la disponibilité agrégée du marché "
        "entre les différentes observations."
    ),
)

history = horizon[
    [
        "snapshot_date",
        "market_availability_rate_30d_pct",
        "market_availability_rate_60d_pct",
        "market_availability_rate_90d_pct",
        "market_availability_rate_365d_pct",
    ]
].copy()

history = history.sort_values(
    "snapshot_date"
)

history["date_label"] = (
    history["snapshot_date"]
    .apply(format_date_fr)
)

history_order = (
    history["date_label"]
    .tolist()
)

history_long = history.melt(
    id_vars=[
        "snapshot_date",
        "date_label",
    ],
    value_vars=[
        "market_availability_rate_30d_pct",
        "market_availability_rate_60d_pct",
        "market_availability_rate_90d_pct",
        "market_availability_rate_365d_pct",
    ],
    var_name="horizon",
    value_name="availability",
)

history_long["horizon_label"] = (
    history_long["horizon"].map(
        {
            "market_availability_rate_30d_pct": "30 jours",
            "market_availability_rate_60d_pct": "60 jours",
            "market_availability_rate_90d_pct": "90 jours",
            "market_availability_rate_365d_pct": "365 jours",
        }
    )
)

history_chart = (
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
            "availability:Q",
            title="Disponibilité (%)",
            scale=alt.Scale(
                domain=[0, 100],
            ),
        ),
        color=alt.Color(
            "horizon_label:N",
            title=None,
            sort=[
                "30 jours",
                "60 jours",
                "90 jours",
                "365 jours",
            ],
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
                "horizon_label:N",
                title="Horizon",
            ),
            alt.Tooltip(
                "availability:Q",
                title="Disponibilité",
                format=".1f",
            ),
        ],
    )
    .properties(height=310)
)

st.altair_chart(
    history_chart,
    use_container_width=True,
)

note(
    "Chaque point correspond à l'état du calendrier futur visible "
    "au moment du snapshot. Deux observations successives ne portent "
    "donc pas exactement sur les mêmes dates futures."
)

st.divider()

# ============================================================
# Seasonality
# ============================================================

section_header(
    "Saisonnalité du calendrier",
    (
        "Disponibilité future mois par mois telle qu'elle était "
        "visible depuis le snapshot sélectionné."
    ),
)

current_monthly = monthly[
    monthly["snapshot_date"] == selected_snapshot
].copy()

current_monthly = current_monthly.sort_values(
    "calendar_month"
)

if current_monthly.empty:
    st.info(
        "Aucune donnée mensuelle de calendrier n'est disponible "
        "pour cette observation."
    )

else:
    current_monthly["month_label"] = (
        current_monthly["calendar_month"]
        .apply(format_month_fr)
    )

    month_order = (
        current_monthly["month_label"]
        .tolist()
    )

    seasonality_data = current_monthly[
        [
            "calendar_month",
            "month_label",
            "market_availability_rate_pct",
            "median_listing_availability_rate_pct",
        ]
    ].copy()

    seasonality_long = seasonality_data.melt(
        id_vars=[
            "calendar_month",
            "month_label",
        ],
        value_vars=[
            "market_availability_rate_pct",
            "median_listing_availability_rate_pct",
        ],
        var_name="metric",
        value_name="availability",
    )

    seasonality_long["metric_label"] = (
        seasonality_long["metric"].map(
            {
                "market_availability_rate_pct":
                    "Marché",
                "median_listing_availability_rate_pct":
                    "Annonce médiane",
            }
        )
    )

    seasonality_chart = (
        alt.Chart(seasonality_long)
        .mark_line(
            point=alt.OverlayMarkDef(
                filled=True,
                size=60,
            ),
            strokeWidth=2.5,
        )
        .encode(
            x=alt.X(
                "month_label:N",
                sort=month_order,
                title="Mois du calendrier",
                axis=alt.Axis(
                    labelAngle=-35,
                    labelPadding=8,
                ),
            ),
            y=alt.Y(
                "availability:Q",
                title="Disponibilité (%)",
                scale=alt.Scale(
                    domain=[0, 100],
                ),
            ),
            color=alt.Color(
                "metric_label:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Marché",
                        "Annonce médiane",
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
                    "month_label:N",
                    title="Mois",
                ),
                alt.Tooltip(
                    "metric_label:N",
                    title="Indicateur",
                ),
                alt.Tooltip(
                    "availability:Q",
                    title="Disponibilité",
                    format=".1f",
                ),
            ],
        )
        .properties(height=320)
    )

    st.altair_chart(
        seasonality_chart,
        use_container_width=True,
    )

    zero_median_months = current_monthly[
        current_monthly[
            "median_listing_availability_rate_pct"
        ].fillna(-1) == 0
    ]

    if not zero_median_months.empty:
        note(
            "Une disponibilité médiane de 0 % signifie qu'au moins "
            "la moitié des annonces représentées pour le mois concerné "
            "ont un taux de disponibilité nul. Elle ne signifie pas "
            "que l'ensemble du marché est indisponible ou réservé."
        )

        note(
            "Les mois situés aux extrémités de la fenêtre peuvent être "
            "partiellement représentés. La couverture détaillée ci-dessous "
            "doit être prise en compte avant de comparer leurs niveaux "
            "de disponibilité."
        )

    st.divider()

    # ========================================================
    # Monthly coverage
    # ========================================================

    section_header(
        "Couverture des mois représentés",
        (
            "Qualité de représentation du calendrier pour "
            "interpréter correctement les indicateurs mensuels."
        ),
    )

    monthly_detail = current_monthly[
        [
            "month_label",
            "listing_count",
            "represented_listing_days",
            "listing_day_coverage_pct",
            "full_month_listing_share_pct",
            "market_availability_rate_pct",
            "median_listing_availability_rate_pct",
            "is_full_month_coverage",
        ]
    ].copy()

    monthly_detail.columns = [
        "Mois",
        "Annonces",
        "Journées représentées",
        "Couverture calendrier",
        "Annonces mois complet",
        "Disponibilité marché",
        "Disponibilité médiane",
        "Mois complet",
    ]

    for column in (
        "Couverture calendrier",
        "Annonces mois complet",
        "Disponibilité marché",
        "Disponibilité médiane",
    ):
        monthly_detail[column] = (
            monthly_detail[column]
            .apply(format_percent)
        )

    st.dataframe(
        monthly_detail,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Annonces": st.column_config.NumberColumn(
                format="localized",
            ),
            "Journées représentées": st.column_config.NumberColumn(
                format="localized",
            ),
            "Mois complet": st.column_config.CheckboxColumn(),
        },
    )

    partial_months = current_monthly[
        ~current_monthly[
            "is_full_month_coverage"
        ].fillna(False)
    ]

    if not partial_months.empty:
        insight_box(
            "Couverture mensuelle partielle",
            (
                "Certains mois ne sont que partiellement représentés "
                "dans le calendrier disponible. Les niveaux de "
                "disponibilité de ces mois doivent donc être lus "
                "conjointement avec leur couverture."
            ),
        )

# ============================================================
# Methodology
# ============================================================

st.divider()

with st.expander(
    "Comment interpréter la disponibilité ?"
):
    st.markdown(
        """
**Disponibilité déclarée**

Les données de calendrier Inside Airbnb indiquent si une date future
est marquée comme disponible ou indisponible pour une annonce.

Une journée indisponible ne signifie donc pas nécessairement qu'une
réservation a effectivement eu lieu.

**Disponibilité du marché**

Elle correspond au rapport entre le nombre total de journées
disponibles et le nombre total de journées représentées.

**Annonce moyenne et annonce médiane**

La moyenne et la médiane sont calculées à partir du taux de
disponibilité propre à chaque annonce. La médiane décrit le niveau
de disponibilité de l'annonce située au centre de la distribution.

Une médiane de 0 % signifie qu'au moins la moitié des annonces
considérées ont une disponibilité nulle sur la période. Elle ne
signifie pas que 100 % des annonces du marché sont indisponibles.

**Horizons 30 / 60 / 90 / 365 jours**

Les horizons sont reconstruits à partir de la première date
effectivement présente dans le calendrier de chaque snapshot.

**Évolution historique**

Chaque snapshot observe un calendrier futur à une date différente.
Les évolutions entre snapshots décrivent donc l'état du calendrier
visible à chaque observation et non l'évolution d'une période
calendaire strictement identique.

**Saisonnalité**

Les indicateurs mensuels décrivent le calendrier futur visible au
moment de chaque observation. Les mois situés aux extrémités de la
fenêtre peuvent être partiellement couverts.

La couverture mensuelle doit être prise en compte avant de comparer
les niveaux de disponibilité entre les mois.

**Limite d'interprétation**

Ces indicateurs décrivent une disponibilité déclarée dans le
calendrier Airbnb. Ils ne doivent pas être interprétés comme des
taux d'occupation observés ou comme une mesure directe du nombre
de réservations.
        """
    )