"""Comparateur temporel — Inside Airbnb Analytics."""

import altair as alt
import pandas as pd
import streamlit as st

from ui.config import MARTS, get_session
from ui.components import page_header, section_header
from ui.formatters import format_date_fr
from ui.sidebar import format_location_name, render_sidebar
from ui.styles import apply_global_styles


# ============================================================
# Configuration
# ============================================================

apply_global_styles()

CHART_BLUE = "#356DCC"
CHART_LIGHT_BLUE = "#79B8F3"

HORIZONS = {
    "30 jours": "MARKET_AVAILABILITY_RATE_30D_PCT",
    "60 jours": "MARKET_AVAILABILITY_RATE_60D_PCT",
    "90 jours": "MARKET_AVAILABILITY_RATE_90D_PCT",
    "365 jours": "MARKET_AVAILABILITY_RATE_365D_PCT",
}

INDICATORS = {
    "Nombre d'annonces": ("LISTING_COUNT", "", 0),
    "Prix médian": ("MEDIAN_PRICE", " €", 2),
    "Couverture tarifaire": ("COVERAGE", " %", 1),
}


# ============================================================
# Helpers
# ============================================================

def location_slug(value) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "-")
        .replace("_", "-")
    )

def is_valid(value):
    """Return True when a scalar is available."""
    return value is not None and bool(pd.notna(value))


def format_value(value, suffix="", decimals=0, signed=False):
    """Format numbers in French without converting missing data to zero."""
    if not is_valid(value):
        return "N/D"

    number = float(value)
    prefix = "+" if signed and number > 0 else ""
    formatted = f"{number:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{prefix}{formatted}{suffix}"


def calculate_change(previous, current):
    """Return absolute and relative changes, when computable."""
    if not is_valid(previous) or not is_valid(current):
        return None, None

    previous, current = float(previous), float(current)
    absolute = current - previous
    relative = absolute / previous * 100 if previous != 0 else None
    return absolute, relative


def price_coverage(priced, total):
    if not is_valid(priced) or not is_valid(total) or float(total) <= 0:
        return None
    return 100 * float(priced) / float(total)


def normalize_dates(frame):
    if not frame.empty:
        frame["SNAPSHOT_DATE"] = pd.to_datetime(frame["SNAPSHOT_DATE"]).dt.date
    return frame


def render_metric(label, column, reference, comparison, reference_date,
                  comparison_date, suffix="", decimals=0, points=False):
    """Display a compact KPI card with an unambiguous change."""
    previous = reference[column]
    current = comparison[column]
    absolute, relative = calculate_change(previous, current)
    if column == "MEDIAN_PRICE" and (
        price_coverage(reference["LISTINGS_WITH_PRICE"], reference["LISTING_COUNT"]) in (None, 0)
        or price_coverage(comparison["LISTINGS_WITH_PRICE"], comparison["LISTING_COUNT"]) in (None, 0)
    ):
        absolute, relative = None, None

    with st.container(border=True):
        st.markdown(f"**{label}**")
        left, right = st.columns(2, gap="small")
        with left:
            st.caption(format_date_fr(reference_date))
            st.markdown(f"### {format_value(previous, suffix, decimals)}")
        with right:
            st.caption(format_date_fr(comparison_date))
            st.markdown(f"### {format_value(current, suffix, decimals)}")

        if points:
            caption = "Écart : " + format_value(absolute, " pt", 1, signed=True)
        else:
            caption = "Variation : " + format_value(relative, " %", 1, signed=True)
        st.caption(caption)


def grouped_chart(frame, category, value, order=None, horizontal=False, height=350):
    """Accessible grouped Altair chart, consistent across both comparisons."""
    periods = [format_date_fr(date_a), format_date_fr(date_b)]
    colors = alt.Color(
        "Période:N",
        title=None,
        sort=periods,
        scale=alt.Scale(domain=periods, range=[CHART_BLUE, CHART_LIGHT_BLUE]),
        legend=alt.Legend(orient="bottom", direction="horizontal", labelFontSize=12),
    )
    tooltips = [
        alt.Tooltip(f"{category}:N", title=category),
        alt.Tooltip("Période:N", title="Observation"),
        alt.Tooltip(f"{value}:Q", title=value, format=",.1f"),
    ]
    base = alt.Chart(frame).mark_bar(cornerRadiusEnd=3).encode(
        color=colors,
        tooltip=tooltips,
    )
    if horizontal:
        # A single selected zone should not occupy a huge blank chart.
        base = base.encode(
            y=alt.Y(f"{category}:N", sort=order, title=None,
                    axis=alt.Axis(labelLimit=210, labelPadding=12, labelFontSize=12)),
            yOffset=alt.YOffset("Période:N", sort=periods),
            x=alt.X(f"{value}:Q", title=value,
                    scale=alt.Scale(zero=True), axis=alt.Axis(tickCount=6)),
        )
    else:
        base = base.encode(
            x=alt.X(f"{category}:N", sort=order, title=None,
                    axis=alt.Axis(labelAngle=0, labelPadding=12, labelFontSize=12)),
            xOffset=alt.XOffset("Période:N", sort=periods),
            y=alt.Y(f"{value}:Q", title=value,
                    scale=alt.Scale(zero=True), axis=alt.Axis(tickCount=6)),
        )
    st.altair_chart(base.properties(height=height).configure_view(stroke=None),
                    use_container_width=True)


# ============================================================
# Data access
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def load_data():
    session = get_session()

    market = session.sql(
        f"""
        SELECT
            m.SOURCE_COUNTRY,
            m.SOURCE_CITY,
            m.SNAPSHOT_DATE,
            m.LISTING_COUNT,
            m.LISTINGS_WITH_PRICE,
            m.MEDIAN_PRICE,
            m.AVERAGE_AVAILABILITY_30,
            h.HOST_COUNT,
            h.MULTI_LISTING_HOST_SHARE_PCT,
            h.HOST_HHI
        FROM {MARTS}.MART_MARKET_SNAPSHOT AS m
        LEFT JOIN {MARTS}.MART_HOST_SNAPSHOT AS h
            ON m.SOURCE_COUNTRY = h.SOURCE_COUNTRY
           AND m.SOURCE_CITY = h.SOURCE_CITY
           AND m.SNAPSHOT_DATE = h.SNAPSHOT_DATE
        ORDER BY
            m.SOURCE_COUNTRY,
            m.SOURCE_CITY,
            m.SNAPSHOT_DATE
        """
    ).to_pandas()

    availability = session.sql(
        f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            {', '.join(HORIZONS.values())}
        FROM {MARTS}.MART_AVAILABILITY_HORIZON_SNAPSHOT
        ORDER BY
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE
        """
    ).to_pandas()

    neighbourhoods = session.sql(
        f"""
        SELECT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            NEIGHBOURHOOD,
            LISTING_COUNT,
            LISTINGS_WITH_PRICE,
            MEDIAN_PRICE
        FROM {MARTS}.MART_NEIGHBOURHOOD_SNAPSHOT
        WHERE NEIGHBOURHOOD IS NOT NULL
        ORDER BY
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE,
            NEIGHBOURHOOD
        """
    ).to_pandas()

    return tuple(
        map(
            normalize_dates,
            (
                market,
                availability,
                neighbourhoods,
            ),
        )
    )

# ============================================================
# Page header and periods
# ============================================================

(
    selected_country,
    selected_city,
    _,
) = render_sidebar()

country_key = str(
    selected_country
).strip().lower()

city_key = str(
    selected_city
).strip().lower()

city_label = format_location_name(
    selected_city
)

country_label = format_location_name(
    selected_country
)

location_label = (
    f"{city_label}, {country_label}"
)

try:
    market, availability, neighbourhoods = load_data()
except Exception as error:
    st.error(f"Impossible de charger les données : {error}")
    st.stop()

def filter_location(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame

    return frame.loc[
        frame["SOURCE_COUNTRY"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq(country_key)
        &
        frame["SOURCE_CITY"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq(city_key)
    ].copy()


market = filter_location(market)
availability = filter_location(availability)
neighbourhoods = filter_location(neighbourhoods)

if len(market) < 2:
    st.warning(
        "Au moins deux observations historiques sont nécessaires "
        f"pour comparer {location_label}."
    )
    st.stop()

dates = sorted(market["SNAPSHOT_DATE"].dropna().unique())

page_header(
    title="Comparateur temporel",
    subtitle=(
        "Analyse comparative des observations historiques du marché "
        f"de la location courte durée à {city_label}."
    ),
    icon="🔄",
    badges=[
        f"📍 {location_label}",
        f"🗓️ {len(dates)} observations historiques",
    ],
)

section_header(
    "Comparaison des zones",
    (
        "Comparez le volume d'annonces, le prix médian "
        "et la couverture tarifaire par zone géographique."
    ),
)

left, right = st.columns(2)
with left:
    date_a = st.selectbox(
        "Période de référence",
        dates,
        index=0,
        format_func=format_date_fr,
        key="comparison_date_a",
    )
with right:
    date_b = st.selectbox(
        "Période comparée",
        dates,
        index=len(dates) - 1,
        format_func=format_date_fr,
        key="comparison_date_b",
    )

if date_a == date_b:
    st.info("Sélectionnez deux dates différentes pour calculer les variations.")
    st.stop()

row_a = market.loc[market["SNAPSHOT_DATE"] == date_a].iloc[0]
row_b = market.loc[market["SNAPSHOT_DATE"] == date_b].iloc[0]


# ============================================================
# Main indicators
# ============================================================

st.divider()
section_header(
    "Évolution des indicateurs",
    "Les variations portent sur les observations sélectionnées, pas nécessairement sur les mêmes annonces.",
)

metric_specs = [
    ("Annonces observées", "LISTING_COUNT", "", 0, False),
    ("Prix médian", "MEDIAN_PRICE", " €", 2, False),
    ("Disponibilité moyenne à 30 jours", "AVERAGE_AVAILABILITY_30", " jours", 1, False),
    ("Hôtes observés", "HOST_COUNT", "", 0, False),
    ("Part des hôtes multi-annonces", "MULTI_LISTING_HOST_SHARE_PCT", " %", 1, True),
    ("Concentration des annonces (HHI)", "HOST_HHI", "", 2, False),
]

for start in (0, 3):
    for container, spec in zip(st.columns(3, gap="large"), metric_specs[start:start + 3]):
        with container:
            render_metric(
                spec[0], spec[1], row_a, row_b, date_a, date_b,
                suffix=spec[2], decimals=spec[3], points=spec[4],
            )
    if start == 0:
        st.write("")


# ============================================================
# Price coverage
# ============================================================

st.divider()
section_header(
    "Couverture tarifaire",
    "Part des annonces disposant d'un prix exploitable. Une donnée absente n'est pas un prix nul.",
)

coverage_a = price_coverage(row_a["LISTINGS_WITH_PRICE"], row_a["LISTING_COUNT"])
coverage_b = price_coverage(row_b["LISTINGS_WITH_PRICE"], row_b["LISTING_COUNT"])

coverage_rows = []
for date, row, coverage in (
    (date_a, row_a, coverage_a),
    (date_b, row_b, coverage_b),
):
    coverage_rows.append({
        "Période": format_date_fr(date),
        "Annonces observées": format_value(row["LISTING_COUNT"]),
        "Annonces avec prix": format_value(row["LISTINGS_WITH_PRICE"]),
        "Couverture tarifaire": format_value(coverage, " %", 1),
        "Prix médian": format_value(row["MEDIAN_PRICE"], " €", 2),
    })

st.dataframe(pd.DataFrame(coverage_rows), hide_index=True, use_container_width=True)

if (coverage_a is not None and coverage_b is not None
        and coverage_a > 0 and coverage_b > 0):
    st.caption(
        "Écart de couverture : "
        + format_value(coverage_b - coverage_a, " pt", 1, signed=True)
    )
else:
    st.info(
        "Couverture tarifaire non comparable : aucune donnée tarifaire "
        "exploitable pour au moins une des périodes."
    )


# ============================================================
# Availability horizons
# ============================================================

st.divider()
section_header(
    "Disponibilité selon l'horizon",
    "Part des journées déclarées disponibles : il ne s'agit pas d'un taux d'occupation.",
)

av_a = availability.loc[availability["SNAPSHOT_DATE"] == date_a]
av_b = availability.loc[availability["SNAPSHOT_DATE"] == date_b]

if av_a.empty or av_b.empty:
    st.info("Données de disponibilité insuffisantes pour les périodes choisies.")
else:
    av_a, av_b = av_a.iloc[0], av_b.iloc[0]
    chart_rows, detail_rows = [], []

    for label, column in HORIZONS.items():
        previous, current = av_a[column], av_b[column]
        difference, _ = calculate_change(previous, current)

        for date, value in ((date_a, previous), (date_b, current)):
            chart_rows.append({
                "Horizon": label,
                "Période": format_date_fr(date),
                "Disponibilité (%)": float(value) if is_valid(value) else None,
            })

        detail_rows.append({
            "Horizon": label,
            format_date_fr(date_a): format_value(previous, " %", 1),
            format_date_fr(date_b): format_value(current, " %", 1),
            "Écart (points de %)": format_value(difference, " pt", 1, signed=True),
        })

    chart_df = pd.DataFrame(chart_rows).dropna(subset=["Disponibilité (%)"])
    if not chart_df.empty:
        grouped_chart(
            chart_df, "Horizon", "Disponibilité (%)",
            order=list(HORIZONS), height=300,
        )
    else:
        st.info("Aucun taux de disponibilité exploitable.")

    st.dataframe(pd.DataFrame(detail_rows), hide_index=True, use_container_width=True)
    st.caption("Les écarts sont exprimés en points de pourcentage.")


# ============================================================
# Neighbourhood comparison and export
# ============================================================

st.divider()
section_header(
    "Comparaison des quartiers",
    "Comparez le volume d'annonces, le prix médian et la couverture tarifaire par zone.",
)

neighbourhood_a = neighbourhoods.loc[
    neighbourhoods["SNAPSHOT_DATE"] == date_a
].set_index("NEIGHBOURHOOD")
neighbourhood_b = neighbourhoods.loc[
    neighbourhoods["SNAPSHOT_DATE"] == date_b
].set_index("NEIGHBOURHOOD")

common = sorted(set(neighbourhood_a.index) & set(neighbourhood_b.index))

if not common:
    st.info("Aucune zone commune aux deux observations.")
else:
    st.caption("Ce filtre concerne uniquement les graphiques et tableaux de cette section.")
    selected = st.multiselect(
        "Zones à comparer",
        options=common,
        default=common,
        key="comparison_neighbourhoods",
    )

    filter_left, filter_right = st.columns([2, 1])
    with filter_left:
        indicator = st.radio(
            "Indicateur",
            options=list(INDICATORS),
            horizontal=True,
        )
    with filter_right:
        sort_by = st.selectbox(
            "Classement",
            ["Écart absolu décroissant", "Écart absolu croissant", "Nom de la zone"],
        )

    indicator_column, suffix, decimals = INDICATORS[indicator]
    records = []

    for name in selected:
        previous = neighbourhood_a.loc[name]
        current = neighbourhood_b.loc[name]

        if isinstance(previous, pd.DataFrame) or isinstance(current, pd.DataFrame):
            st.error("Plusieurs lignes par quartier et date : vérifiez le grain du mart.")
            st.stop()

        previous_coverage = price_coverage(
            previous["LISTINGS_WITH_PRICE"], previous["LISTING_COUNT"]
        )
        current_coverage = price_coverage(
            current["LISTINGS_WITH_PRICE"], current["LISTING_COUNT"]
        )

        if indicator_column == "COVERAGE":
            previous_value, current_value = previous_coverage, current_coverage
        else:
            previous_value = previous[indicator_column]
            current_value = current[indicator_column]

        # Missing price coverage is not evidence of a zero market price.
        if indicator_column == "MEDIAN_PRICE":
            if previous_coverage is None or previous_coverage == 0:
                previous_value = None
            if current_coverage is None or current_coverage == 0:
                current_value = None

        absolute, relative = calculate_change(previous_value, current_value)
        if indicator_column == "COVERAGE" and (
            previous_coverage == 0 or current_coverage == 0
        ):
            absolute, relative = None, None

        records.append({
            "Quartier": name,
            "Référence": previous_value,
            "Comparaison": current_value,
            "Écart": absolute,
            "Variation relative (%)": relative,
            "Prix médian initial": previous["MEDIAN_PRICE"],
            "Prix médian comparé": current["MEDIAN_PRICE"],
            "Couverture initiale (%)": previous_coverage,
            "Couverture comparée (%)": current_coverage,
        })

    details = pd.DataFrame(records)

    if details.empty:
        st.info("Sélectionnez au moins un quartier.")
    else:
        if sort_by == "Nom de la zone":
            details = details.sort_values("Quartier")
        else:
            details = details.assign(amplitude=details["Écart"].abs())
            details = details.sort_values(
                "amplitude", ascending=(sort_by == "Écart absolu croissant"),
                na_position="last",
            ).drop(columns="amplitude")

        chart_rows = details.melt(
            id_vars="Quartier",
            value_vars=["Référence", "Comparaison"],
            var_name="Observation",
            value_name=indicator,
        ).dropna(subset=[indicator])
        chart_rows["Période"] = chart_rows["Observation"].map({
            "Référence": format_date_fr(date_a),
            "Comparaison": format_date_fr(date_b),
        })

        if chart_rows.empty:
            st.info("Aucune donnée exploitable pour cet indicateur.")
        else:
            grouped_chart(
                chart_rows, "Quartier", indicator,
                order=details["Quartier"].tolist(),
                horizontal=True,
                height=max(130, 48 * len(details)),
            )

        delta_suffix = " pt" if indicator_column == "COVERAGE" else suffix
        view = pd.DataFrame({
            "Zone": details["Quartier"],
            format_date_fr(date_a): details["Référence"].map(
                lambda value: format_value(value, suffix, decimals)
            ),
            format_date_fr(date_b): details["Comparaison"].map(
                lambda value: format_value(value, suffix, decimals)
            ),
            "Écart": details["Écart"].map(
                lambda value: format_value(value, delta_suffix, decimals, signed=True)
            ),
            "Variation relative": details["Variation relative (%)"].map(
                lambda value: format_value(value, " %", 1, signed=True)
            ),
            "Prix médian initial": details["Prix médian initial"].map(
                lambda value: format_value(value, " €", 2)
            ),
            "Prix médian comparé": details["Prix médian comparé"].map(
                lambda value: format_value(value, " €", 2)
            ),
            "Couverture initiale": details["Couverture initiale (%)"].map(
                lambda value: format_value(value, " %", 1)
            ),
            "Couverture comparée": details["Couverture comparée (%)"].map(
                lambda value: format_value(value, " %", 1)
            ),
        })
        st.markdown("**Détail des zones sélectionnées**")
        st.dataframe(view, hide_index=True, use_container_width=True)

        export = details.copy()
        export.insert(1, "Date de référence", str(date_a))
        export.insert(2, "Date comparée", str(date_b))
        export.insert(3, "Indicateur", indicator)
        st.download_button(
            "Exporter les zones (CSV)",
            data=export.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
            file_name=(
                f"comparaison_zones_"
                f"{location_slug(selected_country)}_"
                f"{location_slug(selected_city)}_"
                f"{date_a}_{date_b}.csv"
            ),
            mime="text/csv",
        )
        st.caption(
            "Seuls les zones présentes aux deux dates sont comparés. "
            "Les prix médians concernent uniquement les annonces avec prix exploitable."
        )


# ============================================================
# Methodological warnings
# ============================================================

st.divider()
section_header("Points de vigilance")

if (
    not is_valid(row_a["MEDIAN_PRICE"])
    or not is_valid(row_b["MEDIAN_PRICE"])
    or coverage_a == 0
    or coverage_b == 0
):
    st.warning(
        "Le prix médian est indisponible pour au moins une période. "
        "Aucune variation tarifaire globale n'est calculée."
    )

_, listing_change_pct = calculate_change(row_a["LISTING_COUNT"], row_b["LISTING_COUNT"])
if listing_change_pct is not None and abs(listing_change_pct) >= 25:
    st.warning(
        "Le nombre d'annonces varie d'au moins 25 % entre les deux observations. "
        "Les populations comparées peuvent être différentes."
    )

st.caption(
    f"Source : Inside Airbnb · {location_label}. "
    "Ces résultats décrivent les observations disponibles "
    "et ne constituent pas une mesure exhaustive du marché. "
    "Les calendriers indiquent une disponibilité déclarée, "
    "pas des réservations."
)