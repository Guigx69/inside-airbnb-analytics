import streamlit as st

from ui.config import MARTS, get_session
from ui.formatters import format_date_fr


@st.cache_data(ttl=3600)
def load_available_locations():
    """Return the geographic observations available in the marts."""

    session = get_session()

    locations = session.sql(
        f"""
        SELECT DISTINCT
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE
        FROM {MARTS}.MART_MARKET_SNAPSHOT
        WHERE SOURCE_COUNTRY IS NOT NULL
          AND SOURCE_CITY IS NOT NULL
          AND SNAPSHOT_DATE IS NOT NULL
        ORDER BY
            SOURCE_COUNTRY,
            SOURCE_CITY,
            SNAPSHOT_DATE
        """
    ).to_pandas()

    locations.columns = locations.columns.str.lower()

    return locations


def format_location_name(value):
    """Return a user-friendly geographic label."""

    return str(value).replace("-", " ").title()


def render_sidebar():
    """Render the global geographic context.

    Returns:
        tuple: selected country, city and snapshot date.
    """

    locations = load_available_locations()

    if locations.empty:
        st.error(
            "Aucune observation géographique n'est disponible."
        )
        st.stop()

    # ========================================================
    # Country
    # ========================================================

    countries = sorted(
        locations["source_country"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_country = st.sidebar.selectbox(
        "Pays",
        options=countries,
        format_func=format_location_name,
        key="global_source_country",
    )

    country_locations = locations[
        locations["source_country"] == selected_country
    ]

    # ========================================================
    # Location
    # ========================================================

    cities = sorted(
        country_locations["source_city"]
        .dropna()
        .unique()
        .tolist()
    )

    selected_city = st.sidebar.selectbox(
        "Location",
        options=cities,
        format_func=format_location_name,
        key="global_source_city",
    )

    selected_location = country_locations[
        country_locations["source_city"] == selected_city
    ]

    # ========================================================
    # Snapshot
    # ========================================================

    snapshot_dates = sorted(
        selected_location["snapshot_date"]
        .dropna()
        .unique()
        .tolist()
    )

    if not snapshot_dates:
        st.error(
            "Aucune observation n'est disponible "
            "pour cette localisation."
        )
        st.stop()

    st.sidebar.caption("OBSERVATION")

    selected_snapshot = st.sidebar.selectbox(
        "Snapshot",
        options=snapshot_dates,
        index=len(snapshot_dates) - 1,
        format_func=lambda value: (
            f"📅 {format_date_fr(value)}"
        ),
        key="global_snapshot_date",
    )

    # ========================================================
    # Context
    # ========================================================

    st.sidebar.divider()

    st.sidebar.markdown(
        f"**📍 {format_location_name(selected_city)}, "
        f"{format_location_name(selected_country)}**"
    )

    st.sidebar.caption(
        f"Inside Airbnb · "
        f"{len(snapshot_dates)} observations historiques"
    )

    return (
        selected_country,
        selected_city,
        selected_snapshot,
    )