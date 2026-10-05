"""Cartographie V2.2.9.4 — Inside Airbnb Analytics (Lyon).

Version Snowflake-native :
- vrais contours administratifs depuis REF_LYON_ARRONDISSEMENTS ;
- vue choroplèthe par arrondissement sur les vrais contours administratifs ;
- vue individuelle avec toutes les annonces géolocalisées ;
- aucune dépendance PyPI/CDN supplémentaire.
"""

import json

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from ui.components import page_header, section_header, note
from ui.formatters import format_date_fr, format_integer
from ui.config import (
    DATABASE,
    MARTS_SCHEMA,
    FCT_LISTING_SNAPSHOT,
    REF_LYON_ARRONDISSEMENTS,
    get_session,
)
from ui.sidebar import render_sidebar
from ui.styles import apply_global_styles


# ============================================================
# Configuration
# ============================================================

apply_global_styles()

MART = FCT_LISTING_SNAPSHOT
BOUNDARIES_TABLE = REF_LYON_ARRONDISSEMENTS
BLUE = "#356DCC"

INDICATORS = {
    "Nombre d'annonces": "listing_count",
    "Prix médian (€)": "median_price",
    "Couverture tarifaire (%)": "price_coverage",
}

session = get_session()


# ============================================================
# Helpers
# ============================================================

def fr(value, decimals=0, unit=""):
    if pd.isna(value):
        return "N/D"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",") + unit


def geometry_center(geometry):
    """Centre d'affichage robuste basé sur l'emprise du Polygon/MultiPolygon."""
    coords = []

    def walk(value):
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            coords.append((float(value[0]), float(value[1])))
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(geometry.get("coordinates", []))
    if not coords:
        return None, None

    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def normalise_arrondissement(value):
    """Rapproche '3e Arrondissement' et 'Lyon 3e Arrondissement'."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return text[5:] if text.lower().startswith("lyon ") else text


# ============================================================
# Données Snowflake
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_geo_data():
    columns = {
        row["COLUMN_NAME"].upper()
        for row in session.sql(
            f"""
            SELECT COLUMN_NAME
            FROM {DATABASE}.INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{MARTS_SCHEMA}'
              AND TABLE_NAME = 'FCT_LISTING_SNAPSHOT'
            """
        ).collect()
    }

    required = {"SNAPSHOT_DATE", "NEIGHBOURHOOD"}
    missing = required - columns
    if missing:
        raise ValueError(
            f"Colonnes absentes dans {MART} : {', '.join(sorted(missing))}"
        )

    latitude = next(
        (c for c in ("LATITUDE", "LISTING_LATITUDE", "LAT") if c in columns),
        None,
    )
    longitude = next(
        (c for c in ("LONGITUDE", "LISTING_LONGITUDE", "LON", "LNG") if c in columns),
        None,
    )
    price = next(
        (
            c
            for c in ("PRICE", "PRICE_EUR", "NIGHTLY_PRICE", "PRICE_AMOUNT")
            if c in columns
        ),
        None,
    )
    listing_id = next((c for c in ("LISTING_ID", "ID") if c in columns), None)

    if not latitude or not longitude:
        raise ValueError("LATITUDE/LONGITUDE introuvables dans FCT_LISTING_SNAPSHOT.")
    if not listing_id:
        raise ValueError("LISTING_ID introuvable dans FCT_LISTING_SNAPSHOT.")

    price_sql = f"TRY_TO_DOUBLE(TO_VARCHAR({price}))" if price else "NULL::FLOAT"

    frame = session.sql(
        f"""
        SELECT
            SNAPSHOT_DATE,
            NEIGHBOURHOOD,
            {listing_id} AS LISTING_ID,
            TRY_TO_DOUBLE(TO_VARCHAR({latitude})) AS LATITUDE,
            TRY_TO_DOUBLE(TO_VARCHAR({longitude})) AS LONGITUDE,
            {price_sql} AS PRICE
        FROM {MART}
        WHERE LOWER(SOURCE_CITY) = 'lyon'
          AND LOWER(SOURCE_COUNTRY) = 'france'
          AND {latitude} IS NOT NULL
          AND {longitude} IS NOT NULL
        """
    ).to_pandas()

    frame.columns = frame.columns.str.lower()
    if frame.empty:
        return frame, bool(price)

    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"]).dt.date
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")

    frame = frame.loc[
        frame["latitude"].between(45.55, 45.95)
        & frame["longitude"].between(4.55, 5.15)
        & frame["neighbourhood"].notna()
    ].copy()

    frame["arr_key"] = frame["neighbourhood"].apply(normalise_arrondissement)
    return frame, bool(price)


@st.cache_data(ttl=3600, show_spinner=False)
def load_boundaries():
    df = session.sql(
        f"""
        SELECT
            CODE_INSEE,
            ARRONDISSEMENT,
            ST_ASGEOJSON(GEOMETRY) AS GEOJSON
        FROM {BOUNDARIES_TABLE}
        ORDER BY CODE_INSEE
        """
    ).to_pandas()

    features = []
    centers = []

    for row in df.itertuples(index=False):
        raw = row.GEOJSON
        geometry = json.loads(raw) if isinstance(raw, str) else raw

        arrondissement = str(row.ARRONDISSEMENT)
        arr_key = normalise_arrondissement(arrondissement)
        lon, lat = geometry_center(geometry)

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "code_insee": str(row.CODE_INSEE),
                    "arrondissement": arrondissement,
                    "arr_key": arr_key,
                },
                "geometry": geometry,
            }
        )

        if lon is not None and lat is not None:
            centers.append(
                {
                    "code_insee": str(row.CODE_INSEE),
                    "arrondissement": arrondissement,
                    "arr_key": arr_key,
                    "longitude": lon,
                    "latitude": lat,
                }
            )

    return {"type": "FeatureCollection", "features": features}, pd.DataFrame(centers)


def build_areas(frame):
    grouped = (
        frame.groupby(["neighbourhood", "arr_key"], as_index=False)
        .agg(
            listing_count=("listing_id", "nunique"),
            listings_with_price=("price", lambda s: s.notna().sum()),
            median_price=("price", "median"),
        )
    )
    grouped["price_coverage"] = (
        grouped["listings_with_price"] / grouped["listing_count"] * 100
    )
    return grouped


# ============================================================
# Chargement
# ============================================================

try:
    geo, price_available = load_geo_data()
    boundaries, boundary_centers = load_boundaries()
except Exception as exc:
    st.error(f"Cartographie indisponible : {exc}")
    st.stop()

if geo.empty:
    st.warning("Aucune annonce géolocalisée disponible pour Lyon.")
    st.stop()

if len(boundaries.get("features", [])) != 9:
    st.error(
        "La table REF_LYON_ARRONDISSEMENTS doit contenir exactement "
        "les 9 arrondissements de Lyon."
    )
    st.stop()


# ============================================================
# En-tête et filtres
# ============================================================

snapshot_dates = sorted(
    pd.to_datetime(geo["snapshot_date"].dropna().unique()).tolist()
)

selected_snapshot = pd.Timestamp(
    render_sidebar(snapshot_dates=snapshot_dates)
)
selected_date = selected_snapshot.date()

current = geo.loc[geo["snapshot_date"] == selected_date].copy()

if current.empty:
    st.error("Le snapshot sélectionné ne contient aucune annonce géolocalisée pour Lyon.")
    st.stop()

page_header(
    title="Cartographie",
    subtitle=(
        "Explorez les annonces Airbnb à Lyon sur leurs coordonnées réelles, "
        "avec les contours administratifs officiels des neuf arrondissements."
    ),
    icon="🗺️",
    badges=[
        "🇫🇷 Lyon, France",
        f"🗓️ {format_date_fr(selected_snapshot)}",
        f"📁 {format_integer(len(snapshot_dates))} observations historiques",
    ],
)

section_header(
    "Explorer Lyon",
    "Choisissez l'indicateur cartographique et les arrondissements à analyser.",
)

indicator = st.selectbox(
    "Indicateur",
    list(INDICATORS),
)

names = sorted(current["neighbourhood"].dropna().unique())

selected_names = st.multiselect(
    "Arrondissements",
    names,
    default=names,
    help="Le filtre s'applique à la carte, aux indicateurs et au tableau.",
)

if not selected_names:
    st.info("Sélectionnez au moins un arrondissement.")
    st.stop()

current = current[current["neighbourhood"].isin(selected_names)].copy()
areas = build_areas(current)

if not price_available and indicator != "Nombre d'annonces":
    st.warning("Colonne de prix non identifiée : seul le volume d'annonces est disponible.")
    indicator = "Nombre d'annonces"

if indicator == "Prix médian (€)" and areas["median_price"].isna().all():
    st.info("Aucun prix exploitable pour les arrondissements sélectionnés.")


# ============================================================
# Carte
# ============================================================

st.divider()
section_header(
    "Répartition géographique",
    "Deux lectures complémentaires : une synthèse par arrondissement sur les "
    "contours administratifs officiels, ou toutes les annonces géolocalisées.",
)

map_mode = st.radio(
    "Niveau de lecture",
    ["Par arrondissement", "Annonces individuelles"],
    horizontal=True,
    label_visibility="collapsed",
)

points = current.dropna(subset=["latitude", "longitude"]).copy()

if points.empty:
    st.warning("Aucune annonce géolocalisée valide pour cette sélection.")
    st.stop()

selected_keys = set(points["arr_key"].dropna().unique())
metric_col = INDICATORS[indicator]

# Agrégats + rattachement aux 9 contours officiels.
map_areas = areas.copy()
map_areas["arr_key"] = map_areas["arr_key"].astype(str)

area_lookup = {
    row.arr_key: row
    for row in map_areas.itertuples(index=False)
}

metric_values = pd.to_numeric(map_areas[metric_col], errors="coerce")
valid_metric = metric_values.dropna()
metric_min = float(valid_metric.min()) if not valid_metric.empty else 0.0
metric_max = float(valid_metric.max()) if not valid_metric.empty else 0.0


def choropleth_color(value, selected=True):
    """Palette bleue calculée côté Python pour compatibilité Snowflake."""
    if not selected:
        return [226, 232, 240, 22]

    if value is None or pd.isna(value):
        return [203, 213, 225, 95]

    if metric_max <= metric_min:
        ratio = 0.55
    else:
        ratio = max(0.0, min(1.0, (float(value) - metric_min) / (metric_max - metric_min)))

    # Bleu clair -> bleu soutenu, sans expression Deck.gl dynamique.
    return [
        int(219 - 166 * ratio),
        int(234 - 125 * ratio),
        int(254 - 48 * ratio),
        150,
    ]


map_features = []
for feature in boundaries["features"]:
    props = feature["properties"]
    key = props["arr_key"]
    selected = key in selected_keys
    row = area_lookup.get(key)

    if row is None:
        listing_count = 0
        median_price = None
        price_coverage = None
        metric_value = None
        neighbourhood = key
    else:
        listing_count = int(row.listing_count)
        median_price = row.median_price
        price_coverage = row.price_coverage
        metric_value = getattr(row, metric_col)
        neighbourhood = str(row.neighbourhood)

    if indicator == "Nombre d'annonces":
        metric_label = f"{listing_count:,}".replace(",", " ")
    elif indicator == "Prix médian (€)":
        metric_label = fr(metric_value, 2, " €")
    else:
        metric_label = fr(metric_value, 1, " %")

    map_features.append(
        {
            "type": "Feature",
            "properties": {
                **props,
                "neighbourhood": neighbourhood,
                "listing_count": listing_count,
                "median_price_label": fr(median_price, 2, " €"),
                "coverage_label": fr(price_coverage, 1, " %"),
                "indicator_label": indicator,
                "metric_label": metric_label,
                "fill_color": choropleth_color(metric_value, selected),
                "line_color": (
                    [31, 78, 146, 245]
                    if selected
                    else [148, 163, 184, 100]
                ),
            },
            "geometry": feature["geometry"],
        }
    )

choropleth_geojson = {
    "type": "FeatureCollection",
    "features": map_features,
}

if map_mode == "Par arrondissement":
    layers = [
        pdk.Layer(
            "GeoJsonLayer",
            data=choropleth_geojson,
            stroked=True,
            filled=True,
            get_fill_color="properties.fill_color",
            get_line_color="properties.line_color",
            get_line_width=2,
            line_width_min_pixels=2,
            pickable=True,
            auto_highlight=True,
            highlight_color=[255, 255, 255, 70],
        )
    ]

    tooltip = {
        "html": (
            "<b>{neighbourhood}</b><br/>"
            "{indicator_label} : <b>{metric_label}</b><br/>"
            "Annonces : {listing_count}<br/>"
            "Prix médian : {median_price_label}<br/>"
            "Couverture tarifaire : {coverage_label}"
        ),
        "style": {
            "backgroundColor": "#17243C",
            "color": "white",
            "fontSize": "13px",
        },
    }

else:
    # Les contours restent visibles mais discrets sous les annonces.
    layers = [
        pdk.Layer(
            "GeoJsonLayer",
            data=choropleth_geojson,
            stroked=True,
            filled=False,
            get_line_color=[20, 65, 125, 255],
            get_line_width=4,
            line_width_min_pixels=3,
            line_width_max_pixels=5,
            pickable=False,
        )
    ]

    point_records = [
        {
            "latitude": float(row.latitude),
            "longitude": float(row.longitude),
            "neighbourhood": str(row.neighbourhood),
            "listing_id": str(row.listing_id),
            "price_label": fr(row.price, 2, " €"),
        }
        for row in points.itertuples(index=False)
    ]

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=point_records,
            get_position="[longitude, latitude]",
            get_radius=3.5,
            radius_units="pixels",
            radius_min_pixels=2.5,
            radius_max_pixels=4.5,
            get_fill_color=[39, 103, 199, 155],
            get_line_color=[255, 255, 255, 210],
            stroked=True,
            line_width_min_pixels=1,
            pickable=True,
            auto_highlight=True,
        )
    )

    tooltip = {
        "html": (
            "<b>{neighbourhood}</b><br/>"
            "Annonce : {listing_id}<br/>"
            "Prix : {price_label}"
        ),
        "style": {
            "backgroundColor": "#17243C",
            "color": "white",
            "fontSize": "13px",
        },
    }

if map_mode == "Par arrondissement":
    # Vue volontairement figée : cette carte sert de synthèse thématique.
    # min_zoom == max_zoom bloque le zoom molette / +/-.
    view_state = pdk.ViewState(
        latitude=45.7578,
        longitude=4.8320,
        zoom=11.35,
        min_zoom=11.35,
        max_zoom=11.35,
        pitch=0,
        bearing=0,
    )
else:
    view_state = pdk.ViewState(
        latitude=45.7578,
        longitude=4.8320,
        zoom=11.35,
        min_zoom=9,
        max_zoom=18,
        pitch=0,
        bearing=0,
    )
deck = pdk.Deck(
    layers=layers,
    initial_view_state=view_state,
    map_style="light",
    tooltip=tooltip,
)

# Une clé différente par mode force Streamlit à remonter le composant Deck.
# Ainsi, revenir de la vue individuelle à la vue arrondissement restaure
# immédiatement le cadrage Lyon défini dans initial_view_state.
map_key = (
    "lyon_map_arrondissements"
    if map_mode == "Par arrondissement"
    else "lyon_map_annonces"
)

st.pydeck_chart(
    deck,
    use_container_width=True,
    height=610,
    key=map_key,
)

if map_mode == "Par arrondissement":
    st.caption(
        f"{len(points):,} annonces synthétisées sur {len(areas)} arrondissements. "
        f"La couleur représente : {indicator.lower()}. "
        "La vue est volontairement figée pour conserver un cadrage comparable."
    )
else:
    st.caption(
        f"{len(points):,} annonces affichées, sans échantillonnage. "
        "Zoomez à la molette jusqu'au niveau rue et survolez un point pour le détail."
    )




# ============================================================
# Indicateurs
# ============================================================

st.divider()
section_header(
    "Indicateurs géographiques",
    "Comparez les arrondissements de la sélection.",
)

metric_col = INDICATORS[indicator]

if metric_col == "median_price":
    visible = areas.dropna(subset=[metric_col]).copy()
else:
    visible = areas.copy()

if visible.empty:
    st.info("Aucune valeur exploitable pour cet indicateur.")
else:
    visible = visible.sort_values(metric_col, ascending=False)

    chart = (
        alt.Chart(visible)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            y=alt.Y("neighbourhood:N", sort="-x", title=None),
            x=alt.X(
                f"{metric_col}:Q",
                title=indicator,
                scale=alt.Scale(zero=True),
            ),
            color=alt.value(BLUE),
            tooltip=[
                alt.Tooltip("neighbourhood:N", title="Arrondissement"),
                alt.Tooltip(f"{metric_col}:Q", title=indicator, format=".2f"),
            ],
        )
        .properties(height=max(280, 42 * len(visible)))
    )

    st.altair_chart(chart, use_container_width=True)


# ============================================================
# Tableau et export
# ============================================================

st.divider()
section_header(
    "Détail par arrondissement",
    "Volumes et indicateurs calculés sur les annonces géolocalisées.",
)

table = areas.sort_values("listing_count", ascending=False).rename(
    columns={
        "neighbourhood": "Arrondissement",
        "listing_count": "Annonces géolocalisées",
        "listings_with_price": "Annonces avec prix",
        "median_price": "Prix médian (€)",
        "price_coverage": "Couverture tarifaire (%)",
    }
)

st.dataframe(
    table[
        [
            "Arrondissement",
            "Annonces géolocalisées",
            "Annonces avec prix",
            "Prix médian (€)",
            "Couverture tarifaire (%)",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        "Prix médian (€)": st.column_config.NumberColumn(format="%.2f €"),
        "Couverture tarifaire (%)": st.column_config.NumberColumn(format="%.1f %%"),
    },
)

st.download_button(
    "Exporter les arrondissements géolocalisés (CSV)",
    table.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
    file_name=f"cartographie_lyon_{selected_date}.csv",
    mime="text/csv",
)


# ============================================================
# Méthodologie
# ============================================================

with st.expander("Méthodologie et limites"):
    st.markdown(
        """
        - Les contours sont les géométries administratives chargées dans
          `REF_LYON_ARRONDISSEMENTS` à partir des données géographiques de la
          Métropole de Lyon.
        - En vue individuelle, chaque point correspond à une annonce disposant
          de coordonnées valides dans `FCT_LISTING_SNAPSHOT`.
        - En vue groupée, une bulle synthétise le volume d'annonces de chaque
          arrondissement ; elle ne remplace pas le contour administratif.
        - Les indicateurs de cette page portent uniquement sur les annonces
          géolocalisées et peuvent donc différer légèrement des indicateurs globaux.
        - Les prix manquants ne sont jamais assimilés à des prix nuls.
        - Un calendrier indisponible ne prouve pas qu'un logement a été réservé.
        """
    )
