"""Cartographie — Inside Airbnb Analytics.

Vue multi-localisation Snowflake-native :
- sélection géographique centralisée via la sidebar ;
- contours administratifs depuis REF_GEOGRAPHIC_AREAS ;
- choroplèthe au grain géographique disponible ;
- vue individuelle des annonces géolocalisées ;
- cadrage calculé dynamiquement ;
- aucune dépendance à une ville, un pays ou un schéma Snowflake spécifique.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from ui.components import page_header, section_header
from ui.config import (
    DATABASE,
    MARTS_SCHEMA,
    FCT_LISTING_SNAPSHOT,
    REF_GEOGRAPHIC_AREAS,
    get_session,
)
from ui.formatters import format_date_fr, format_integer
from ui.sidebar import format_location_name, render_sidebar
from ui.styles import apply_global_styles


# ============================================================
# Configuration
# ============================================================

apply_global_styles()

MART = FCT_LISTING_SNAPSHOT
BOUNDARIES_TABLE = REF_GEOGRAPHIC_AREAS

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

    return (
        f"{value:,.{decimals}f}"
        .replace(",", " ")
        .replace(".", ",")
        + unit
    )


def geographic_key(value):
    """Clé déterministe pour rapprocher NEIGHBOURHOOD et AREA_NAME."""

    if pd.isna(value):
        return ""

    text = str(value).strip().lower()

    text = (
        text.replace("œ", "oe")
        .replace("æ", "ae")
        .replace("’", "'")
    )

    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(text.split())


def geometry_coordinates(geometry):
    """Retourne toutes les coordonnées lon/lat d'un Polygon/MultiPolygon."""

    coordinates = []

    if not isinstance(geometry, dict):
        return coordinates

    def walk(value):
        if (
            isinstance(value, list)
            and len(value) >= 2
            and isinstance(value[0], (int, float))
            and isinstance(value[1], (int, float))
        ):
            coordinates.append(
                (
                    float(value[0]),
                    float(value[1]),
                )
            )
            return

        if isinstance(value, list):
            for item in value:
                walk(item)

    walk(
        geometry.get(
            "coordinates",
            [],
        )
    )

    return coordinates


def geometry_center(geometry):
    """Centre d'affichage basé sur l'emprise d'une géométrie."""

    coordinates = geometry_coordinates(
        geometry
    )

    if not coordinates:
        return None, None

    longitudes = [
        longitude
        for longitude, _ in coordinates
    ]

    latitudes = [
        latitude
        for _, latitude in coordinates
    ]

    return (
        (
            min(longitudes)
            + max(longitudes)
        )
        / 2,
        (
            min(latitudes)
            + max(latitudes)
        )
        / 2,
    )


def calculate_view_state(
    boundaries,
    points,
    *,
    locked=False,
):
    """Calcule un cadrage PyDeck à partir des données réellement affichées."""

    longitudes = []
    latitudes = []

    for feature in boundaries.get(
        "features",
        [],
    ):
        for longitude, latitude in geometry_coordinates(
            feature.get(
                "geometry",
                {},
            )
        ):
            longitudes.append(longitude)
            latitudes.append(latitude)

    if not longitudes and not points.empty:
        longitudes = (
            pd.to_numeric(
                points["longitude"],
                errors="coerce",
            )
            .dropna()
            .tolist()
        )

        latitudes = (
            pd.to_numeric(
                points["latitude"],
                errors="coerce",
            )
            .dropna()
            .tolist()
        )

    if not longitudes or not latitudes:
        return pdk.ViewState(
            latitude=0,
            longitude=0,
            zoom=1,
            pitch=0,
            bearing=0,
        )

    min_lon = min(longitudes)
    max_lon = max(longitudes)
    min_lat = min(latitudes)
    max_lat = max(latitudes)

    center_lon = (
        min_lon + max_lon
    ) / 2

    center_lat = (
        min_lat + max_lat
    ) / 2

    lon_span = max(
        max_lon - min_lon,
        0.001,
    )

    lat_span = max(
        max_lat - min_lat,
        0.001,
    )

    # Approximation Web Mercator suffisante pour déterminer
    # automatiquement un niveau de zoom initial cohérent.
    effective_lon_span = lon_span * max(
        math.cos(
            math.radians(center_lat)
        ),
        0.15,
    )

    span = max(
        effective_lon_span,
        lat_span,
    )

    zoom = math.log2(
        360.0 / span
    ) - 1.35

    zoom = max(
        2.0,
        min(
            14.0,
            zoom,
        ),
    )

    if locked:
        return pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=zoom,
            min_zoom=zoom,
            max_zoom=zoom,
            pitch=0,
            bearing=0,
        )

    return pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        min_zoom=max(
            1.0,
            zoom - 4.0,
        ),
        max_zoom=18,
        pitch=0,
        bearing=0,
    )


def location_slug(
    country,
    city,
):
    value = (
        f"{country}_{city}"
        .strip()
        .lower()
    )

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    return value.strip("_")


# ============================================================
# Données Snowflake
# ============================================================


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def get_fct_columns():
    rows = session.sql(
        f"""
        SELECT COLUMN_NAME
        FROM {DATABASE}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{MARTS_SCHEMA}'
          AND TABLE_NAME = 'FCT_LISTING_SNAPSHOT'
        """
    ).collect()

    return {
        row["COLUMN_NAME"].upper()
        for row in rows
    }


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def load_geo_data(
    source_country,
    source_city,
):
    columns = get_fct_columns()

    required = {
        "SOURCE_COUNTRY",
        "SOURCE_CITY",
        "SNAPSHOT_DATE",
        "NEIGHBOURHOOD",
    }

    missing = (
        required - columns
    )

    if missing:
        raise ValueError(
            f"Colonnes absentes dans {MART} : "
            f"{', '.join(sorted(missing))}"
        )

    latitude = next(
        (
            column
            for column in (
                "LATITUDE",
                "LISTING_LATITUDE",
                "LAT",
            )
            if column in columns
        ),
        None,
    )

    longitude = next(
        (
            column
            for column in (
                "LONGITUDE",
                "LISTING_LONGITUDE",
                "LON",
                "LNG",
            )
            if column in columns
        ),
        None,
    )

    price = next(
        (
            column
            for column in (
                "PRICE",
                "PRICE_EUR",
                "NIGHTLY_PRICE",
                "PRICE_AMOUNT",
            )
            if column in columns
        ),
        None,
    )

    listing_id = next(
        (
            column
            for column in (
                "LISTING_ID",
                "ID",
            )
            if column in columns
        ),
        None,
    )

    if not latitude or not longitude:
        raise ValueError(
            "LATITUDE/LONGITUDE introuvables "
            "dans FCT_LISTING_SNAPSHOT."
        )

    if not listing_id:
        raise ValueError(
            "LISTING_ID introuvable "
            "dans FCT_LISTING_SNAPSHOT."
        )

    price_sql = (
        f"TRY_TO_DOUBLE("
        f"TO_VARCHAR({price})"
        f")"
        if price
        else "NULL::FLOAT"
    )

    # Les valeurs de la sidebar proviennent elles-mêmes du mart.
    # On échappe néanmoins les apostrophes avant injection SQL.
    country_sql = (
        str(source_country)
        .replace("'", "''")
    )

    city_sql = (
        str(source_city)
        .replace("'", "''")
    )

    frame = session.sql(
        f"""
        SELECT
            SNAPSHOT_DATE,
            NEIGHBOURHOOD,
            {listing_id} AS LISTING_ID,
            TRY_TO_DOUBLE(
                TO_VARCHAR({latitude})
            ) AS LATITUDE,
            TRY_TO_DOUBLE(
                TO_VARCHAR({longitude})
            ) AS LONGITUDE,
            {price_sql} AS PRICE
        FROM {MART}
        WHERE LOWER(SOURCE_COUNTRY) = LOWER('{country_sql}')
          AND LOWER(SOURCE_CITY) = LOWER('{city_sql}')
          AND {latitude} IS NOT NULL
          AND {longitude} IS NOT NULL
        """
    ).to_pandas()

    frame.columns = (
        frame.columns.str.lower()
    )

    if frame.empty:
        return (
            frame,
            bool(price),
        )

    frame["snapshot_date"] = (
        pd.to_datetime(
            frame["snapshot_date"]
        )
        .dt.date
    )

    frame["latitude"] = pd.to_numeric(
        frame["latitude"],
        errors="coerce",
    )

    frame["longitude"] = pd.to_numeric(
        frame["longitude"],
        errors="coerce",
    )

    frame["price"] = pd.to_numeric(
        frame["price"],
        errors="coerce",
    )

    frame = frame.loc[
        frame["latitude"].between(
            -90,
            90,
        )
        & frame["longitude"].between(
            -180,
            180,
        )
        & frame["neighbourhood"].notna()
    ].copy()

    frame["area_key"] = (
        frame["neighbourhood"]
        .apply(geographic_key)
    )

    return (
        frame,
        bool(price),
    )


@st.cache_data(
    ttl=3600,
    show_spinner=False,
)
def load_boundaries(
    source_country,
    source_city,
):
    country_sql = (
        str(source_country)
        .replace("'", "''")
    )

    city_sql = (
        str(source_city)
        .replace("'", "''")
    )

    frame = session.sql(
        f"""
        SELECT
            AREA_CODE,
            AREA_NAME,
            AREA_LEVEL,
            SOURCE,
            ST_ASGEOJSON(GEOMETRY) AS GEOJSON
        FROM {BOUNDARIES_TABLE}
        WHERE LOWER(SOURCE_COUNTRY) = LOWER('{country_sql}')
          AND LOWER(SOURCE_CITY) = LOWER('{city_sql}')
        ORDER BY AREA_LEVEL, AREA_CODE
        """
    ).to_pandas()

    features = []
    centers = []

    if frame.empty:
        return (
            {
                "type": "FeatureCollection",
                "features": [],
            },
            pd.DataFrame(),
            [],
            [],
        )

    for row in frame.itertuples(
        index=False
    ):
        raw = row.GEOJSON

        geometry = (
            json.loads(raw)
            if isinstance(raw, str)
            else raw
        )

        area_name = str(
            row.AREA_NAME
        )

        area_level = str(
            row.AREA_LEVEL
        )

        area_key = geographic_key(
            area_name
        )

        longitude, latitude = (
            geometry_center(
                geometry
            )
        )

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "area_code":
                        str(row.AREA_CODE),
                    "area_name":
                        area_name,
                    "area_level":
                        area_level,
                    "area_key":
                        area_key,
                    "source":
                        str(row.SOURCE),
                },
                "geometry":
                    geometry,
            }
        )

        if (
            longitude is not None
            and latitude is not None
        ):
            centers.append(
                {
                    "area_code":
                        str(row.AREA_CODE),
                    "area_name":
                        area_name,
                    "area_level":
                        area_level,
                    "area_key":
                        area_key,
                    "longitude":
                        longitude,
                    "latitude":
                        latitude,
                }
            )

    area_levels = sorted(
        {
            feature[
                "properties"
            ][
                "area_level"
            ]
            for feature in features
        }
    )

    sources = sorted(
        {
            feature[
                "properties"
            ][
                "source"
            ]
            for feature in features
        }
    )

    return (
        {
            "type":
                "FeatureCollection",
            "features":
                features,
        },
        pd.DataFrame(
            centers
        ),
        area_levels,
        sources,
    )


def build_areas(frame):
    grouped = (
        frame.groupby(
            [
                "neighbourhood",
                "area_key",
            ],
            as_index=False,
        )
        .agg(
            listing_count=(
                "listing_id",
                "nunique",
            ),
            listings_with_price=(
                "price",
                lambda series:
                    series.notna().sum(),
            ),
            median_price=(
                "price",
                "median",
            ),
        )
    )

    grouped[
        "price_coverage"
    ] = (
        grouped[
            "listings_with_price"
        ]
        / grouped[
            "listing_count"
        ]
        * 100
    )

    return grouped


# ============================================================
# Contexte global
# ============================================================


(
    selected_country,
    selected_city,
    selected_snapshot,
) = render_sidebar()

selected_snapshot = pd.Timestamp(
    selected_snapshot
)

selected_date = (
    selected_snapshot.date()
)

country_label = (
    format_location_name(
        selected_country
    )
)

city_label = (
    format_location_name(
        selected_city
    )
)

location_label = (
    f"{city_label}, {country_label}"
)


# ============================================================
# Chargement
# ============================================================


try:
    geo, price_available = (
        load_geo_data(
            selected_country,
            selected_city,
        )
    )

    (
        boundaries,
        boundary_centers,
        area_levels,
        boundary_sources,
    ) = load_boundaries(
        selected_country,
        selected_city,
    )

except Exception as exc:
    st.error(
        f"Cartographie indisponible : {exc}"
    )
    st.stop()


if geo.empty:
    st.warning(
        "Aucune annonce géolocalisée "
        f"disponible pour {location_label}."
    )
    st.stop()


current = geo.loc[
    geo["snapshot_date"]
    == selected_date
].copy()


if current.empty:
    st.error(
        "Le snapshot sélectionné ne contient "
        "aucune annonce géolocalisée pour "
        f"{location_label}."
    )
    st.stop()


# ============================================================
# En-tête et filtres
# ============================================================


snapshot_dates = sorted(
    pd.to_datetime(
        geo[
            "snapshot_date"
        ]
        .dropna()
        .unique()
    ).tolist()
)


page_header(
    title="Cartographie",
    subtitle=(
        "Explorez les annonces Airbnb "
        f"à {city_label} sur leurs coordonnées réelles "
        "et, lorsqu'ils sont disponibles, "
        "sur les contours géographiques de référence."
    ),
    icon="🗺️",
    badges=[
        f"📍 {location_label}",
        (
            "🗓️ "
            f"{format_date_fr(selected_snapshot)}"
        ),
        (
            "📁 "
            f"{format_integer(len(snapshot_dates))} "
            "snapshots disponibles"
        ),
    ],
)


section_header(
    f"Explorer {city_label}",
    (
        "Choisissez l'indicateur cartographique "
        "et les zones à analyser."
    ),
)


indicator = st.selectbox(
    "Indicateur",
    list(INDICATORS),
)


names = sorted(
    current[
        "neighbourhood"
    ]
    .dropna()
    .unique()
)


selected_names = st.multiselect(
    "Zones",
    names,
    default=names,
    help=(
        "Le filtre s'applique à la carte, "
        "aux indicateurs et au tableau."
    ),
)


if not selected_names:
    st.info(
        "Sélectionnez au moins une zone."
    )
    st.stop()


current = current.loc[
    current[
        "neighbourhood"
    ].isin(
        selected_names
    )
].copy()


areas = build_areas(
    current
)


if (
    not price_available
    and indicator
    != "Nombre d'annonces"
):
    st.warning(
        "Colonne de prix non identifiée : "
        "seul le volume d'annonces est disponible."
    )

    indicator = (
        "Nombre d'annonces"
    )


if (
    indicator
    == "Prix médian (€)"
    and areas[
        "median_price"
    ].isna().all()
):
    st.info(
        "Aucun prix exploitable "
        "pour les zones sélectionnées."
    )


# ============================================================
# Couverture du référentiel
# ============================================================


boundary_keys = {
    feature[
        "properties"
    ][
        "area_key"
    ]
    for feature in boundaries.get(
        "features",
        [],
    )
}


selected_keys = set(
    current[
        "area_key"
    ]
    .dropna()
    .unique()
)


matched_keys = (
    selected_keys
    & boundary_keys
)


missing_boundary_keys = (
    selected_keys
    - boundary_keys
)


has_boundaries = bool(
    boundaries.get(
        "features",
        [],
    )
)


full_boundary_coverage = (
    has_boundaries
    and not missing_boundary_keys
)


if (
    has_boundaries
    and missing_boundary_keys
):
    missing_names = sorted(
        current.loc[
            current[
                "area_key"
            ].isin(
                missing_boundary_keys
            ),
            "neighbourhood",
        ]
        .dropna()
        .unique()
    )

    st.warning(
        "Le référentiel géographique ne couvre pas "
        f"{len(missing_names)} zone(s) de la sélection. "
        "La vue individuelle reste disponible."
    )


if not has_boundaries:
    st.info(
        "Aucun contour géographique de référence "
        f"n'est disponible pour {location_label}. "
        "La carte affiche les annonces individuelles."
    )


# ============================================================
# Carte
# ============================================================


st.divider()

section_header(
    "Répartition géographique",
    (
        "Deux lectures complémentaires : "
        "une synthèse par zone sur les contours "
        "géographiques disponibles et les annonces "
        "géolocalisées individuellement."
    ),
)


map_modes = [
    "Annonces individuelles"
]


if has_boundaries:
    map_modes.insert(
        0,
        "Par zone",
    )


map_mode = st.radio(
    "Niveau de lecture",
    map_modes,
    horizontal=True,
    label_visibility="collapsed",
)


points = current.dropna(
    subset=[
        "latitude",
        "longitude",
    ]
).copy()


if points.empty:
    st.warning(
        "Aucune annonce géolocalisée valide "
        "pour cette sélection."
    )
    st.stop()


metric_col = (
    INDICATORS[indicator]
)


map_areas = areas.copy()

map_areas[
    "area_key"
] = (
    map_areas[
        "area_key"
    ].astype(str)
)


area_lookup = {
    row.area_key: row
    for row in map_areas.itertuples(
        index=False
    )
}


metric_values = pd.to_numeric(
    map_areas[
        metric_col
    ],
    errors="coerce",
)


valid_metric = (
    metric_values.dropna()
)


metric_min = (
    float(
        valid_metric.min()
    )
    if not valid_metric.empty
    else 0.0
)


metric_max = (
    float(
        valid_metric.max()
    )
    if not valid_metric.empty
    else 0.0
)


def choropleth_color(
    value,
    selected=True,
):
    """Palette calculée côté Python pour Snowflake Streamlit."""

    if not selected:
        return [
            226,
            232,
            240,
            22,
        ]

    if (
        value is None
        or pd.isna(value)
    ):
        return [
            203,
            213,
            225,
            95,
        ]

    if metric_max <= metric_min:
        ratio = 0.55
    else:
        ratio = max(
            0.0,
            min(
                1.0,
                (
                    float(value)
                    - metric_min
                )
                / (
                    metric_max
                    - metric_min
                ),
            ),
        )

    return [
        int(
            219
            - 166 * ratio
        ),
        int(
            234
            - 125 * ratio
        ),
        int(
            254
            - 48 * ratio
        ),
        150,
    ]


map_features = []


for feature in boundaries.get(
    "features",
    [],
):
    properties = (
        feature[
            "properties"
        ]
    )

    key = properties[
        "area_key"
    ]

    selected = (
        key in selected_keys
    )

    row = area_lookup.get(
        key
    )

    if row is None:
        listing_count = 0
        median_price = None
        price_coverage = None
        metric_value = None

        neighbourhood = (
            properties[
                "area_name"
            ]
        )

    else:
        listing_count = int(
            row.listing_count
        )

        median_price = (
            row.median_price
        )

        price_coverage = (
            row.price_coverage
        )

        metric_value = getattr(
            row,
            metric_col,
        )

        neighbourhood = str(
            row.neighbourhood
        )

    if (
        indicator
        == "Nombre d'annonces"
    ):
        metric_label = (
            f"{listing_count:,}"
            .replace(
                ",",
                " ",
            )
        )

    elif (
        indicator
        == "Prix médian (€)"
    ):
        metric_label = fr(
            metric_value,
            2,
            " €",
        )

    else:
        metric_label = fr(
            metric_value,
            1,
            " %",
        )

    map_features.append(
        {
            "type":
                "Feature",
            "properties": {
                **properties,
                "neighbourhood":
                    neighbourhood,
                "listing_count":
                    listing_count,
                "median_price_label":
                    fr(
                        median_price,
                        2,
                        " €",
                    ),
                "coverage_label":
                    fr(
                        price_coverage,
                        1,
                        " %",
                    ),
                "indicator_label":
                    indicator,
                "metric_label":
                    metric_label,
                "fill_color":
                    choropleth_color(
                        metric_value,
                        selected,
                    ),
                "line_color": (
                    [
                        31,
                        78,
                        146,
                        245,
                    ]
                    if selected
                    else [
                        148,
                        163,
                        184,
                        100,
                    ]
                ),
            },
            "geometry":
                feature[
                    "geometry"
                ],
        }
    )


choropleth_geojson = {
    "type":
        "FeatureCollection",
    "features":
        map_features,
}


if (
    map_mode == "Par zone"
    and has_boundaries
):
    layers = [
        pdk.Layer(
            "GeoJsonLayer",
            data=choropleth_geojson,
            stroked=True,
            filled=True,
            get_fill_color=(
                "properties.fill_color"
            ),
            get_line_color=(
                "properties.line_color"
            ),
            get_line_width=2,
            line_width_min_pixels=2,
            pickable=True,
            auto_highlight=True,
            highlight_color=[
                255,
                255,
                255,
                70,
            ],
        )
    ]

    tooltip = {
        "html": (
            "<b>{neighbourhood}</b><br/>"
            "{indicator_label} : "
            "<b>{metric_label}</b><br/>"
            "Annonces : {listing_count}<br/>"
            "Prix médian : {median_price_label}<br/>"
            "Couverture tarifaire : {coverage_label}"
        ),
        "style": {
            "backgroundColor":
                "#17243C",
            "color":
                "white",
            "fontSize":
                "13px",
        },
    }

else:
    layers = []

    if has_boundaries:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=choropleth_geojson,
                stroked=True,
                filled=False,
                get_line_color=[
                    20,
                    65,
                    125,
                    255,
                ],
                get_line_width=4,
                line_width_min_pixels=3,
                line_width_max_pixels=5,
                pickable=False,
            )
        )

    point_records = [
        {
            "latitude":
                float(
                    row.latitude
                ),
            "longitude":
                float(
                    row.longitude
                ),
            "neighbourhood":
                str(
                    row.neighbourhood
                ),
            "listing_id":
                str(
                    row.listing_id
                ),
            "price_label":
                fr(
                    row.price,
                    2,
                    " €",
                ),
        }
        for row in points.itertuples(
            index=False
        )
    ]

    layers.append(
        pdk.Layer(
            "ScatterplotLayer",
            data=point_records,
            get_position=(
                "[longitude, latitude]"
            ),
            get_radius=3.5,
            radius_units="pixels",
            radius_min_pixels=2.5,
            radius_max_pixels=4.5,
            get_fill_color=[
                39,
                103,
                199,
                155,
            ],
            get_line_color=[
                255,
                255,
                255,
                210,
            ],
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
            "backgroundColor":
                "#17243C",
            "color":
                "white",
            "fontSize":
                "13px",
        },
    }


view_state = calculate_view_state(
    boundaries,
    points,
    locked=(
        map_mode
        == "Par zone"
    ),
)


deck = pdk.Deck(
    layers=layers,
    initial_view_state=view_state,
    map_style="light",
    tooltip=tooltip,
)


map_key = (
    "cartography_"
    f"{location_slug(selected_country, selected_city)}_"
    f"{location_slug('', map_mode)}"
)


st.pydeck_chart(
    deck,
    use_container_width=True,
    height=610,
    key=map_key,
)


if (
    map_mode == "Par zone"
):
    st.caption(
        f"{len(points):,} annonces synthétisées "
        f"sur {len(areas)} zone(s). "
        f"La couleur représente : {indicator.lower()}. "
        "Le cadrage est calculé automatiquement "
        "à partir du référentiel géographique."
    )

else:
    st.caption(
        f"{len(points):,} annonces affichées, "
        "sans échantillonnage. "
        "Zoomez jusqu'au niveau rue et survolez "
        "un point pour afficher son détail."
    )


# ============================================================
# Qualité de couverture géographique
# ============================================================


if has_boundaries:
    coverage = (
        len(matched_keys)
        / len(selected_keys)
        * 100
        if selected_keys
        else 0
    )

    st.caption(
        "Couverture du référentiel : "
        f"{len(matched_keys)}/{len(selected_keys)} "
        f"zone(s) sélectionnée(s) ({coverage:.1f} %)."
    )


# ============================================================
# Indicateurs
# ============================================================


st.divider()

section_header(
    "Indicateurs géographiques",
    "Comparez les zones de la sélection.",
)


metric_col = (
    INDICATORS[indicator]
)


if (
    metric_col
    == "median_price"
):
    visible = areas.dropna(
        subset=[
            metric_col
        ]
    ).copy()

else:
    visible = (
        areas.copy()
    )


if visible.empty:
    st.info(
        "Aucune valeur exploitable "
        "pour cet indicateur."
    )

else:
    visible = (
        visible.sort_values(
            metric_col,
            ascending=False,
        )
    )

    chart = (
        alt.Chart(
            visible
        )
        .mark_bar(
            cornerRadiusEnd=4
        )
        .encode(
            y=alt.Y(
                "neighbourhood:N",
                sort="-x",
                title=None,
            ),
            x=alt.X(
                f"{metric_col}:Q",
                title=indicator,
                scale=alt.Scale(
                    zero=True
                ),
            ),
            color=alt.value(
                BLUE
            ),
            tooltip=[
                alt.Tooltip(
                    "neighbourhood:N",
                    title="Zone",
                ),
                alt.Tooltip(
                    f"{metric_col}:Q",
                    title=indicator,
                    format=".2f",
                ),
            ],
        )
        .properties(
            height=max(
                280,
                42 * len(visible),
            )
        )
    )

    st.altair_chart(
        chart,
        use_container_width=True,
    )


# ============================================================
# Tableau et export
# ============================================================


st.divider()

section_header(
    "Détail par zone",
    (
        "Volumes et indicateurs calculés "
        "sur les annonces géolocalisées."
    ),
)


table = (
    areas.sort_values(
        "listing_count",
        ascending=False,
    )
    .rename(
        columns={
            "neighbourhood":
                "Zone",
            "listing_count":
                "Annonces géolocalisées",
            "listings_with_price":
                "Annonces avec prix",
            "median_price":
                "Prix médian (€)",
            "price_coverage":
                "Couverture tarifaire (%)",
        }
    )
)


st.dataframe(
    table[
        [
            "Zone",
            "Annonces géolocalisées",
            "Annonces avec prix",
            "Prix médian (€)",
            "Couverture tarifaire (%)",
        ]
    ],
    hide_index=True,
    use_container_width=True,
    column_config={
        "Prix médian (€)":
            st.column_config.NumberColumn(
                format="%.2f €"
            ),
        "Couverture tarifaire (%)":
            st.column_config.NumberColumn(
                format="%.1f %%"
            ),
    },
)


export_slug = location_slug(
    selected_country,
    selected_city,
)


st.download_button(
    "Exporter les zones géolocalisées (CSV)",
    table.to_csv(
        index=False,
        sep=";",
        decimal=",",
    ).encode(
        "utf-8-sig"
    ),
    file_name=(
        f"cartographie_{export_slug}_"
        f"{selected_date}.csv"
    ),
    mime="text/csv",
)


# ============================================================
# Méthodologie
# ============================================================


with st.expander(
    "Méthodologie et limites"
):
    st.markdown(
        """
        - Les contours sont lus depuis `REF_GEOGRAPHIC_AREAS`. Le référentiel
          peut contenir différents niveaux géographiques selon la destination
          (arrondissement, commune, quartier ou autre niveau disponible).
        - Le rapprochement entre les annonces et les contours repose sur le
          libellé géographique normalisé de `NEIGHBOURHOOD` et `AREA_NAME`.
        - En vue individuelle, chaque point correspond à une annonce disposant
          de coordonnées valides dans `FCT_LISTING_SNAPSHOT`.
        - En vue groupée, la couleur du contour représente l'indicateur
          sélectionné pour la zone correspondante.
        - Le cadrage cartographique est calculé automatiquement à partir des
          géométries disponibles ; aucune emprise géographique propre à une
          destination n'est codée dans la page.
        - Les indicateurs portent uniquement sur les annonces géolocalisées et
          peuvent donc différer légèrement des indicateurs globaux.
        - Les prix manquants ne sont jamais assimilés à des prix nuls.
        - Un calendrier indisponible ne prouve pas qu'un logement a été réservé.
        """
    )

    if area_levels:
        st.caption(
            "Niveaux géographiques disponibles : "
            + ", ".join(
                sorted(
                    set(area_levels)
                )
            )
            + "."
        )

    if boundary_sources:
        st.caption(
            "Sources du référentiel : "
            + ", ".join(
                sorted(
                    set(boundary_sources)
                )
            )
            + "."
        )