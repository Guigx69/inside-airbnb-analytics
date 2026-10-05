"""Central configuration for Inside Airbnb Analytics."""

import os

import streamlit as st


def get_session():
    """Return the Snowflake session used by the Streamlit application."""
    connection = st.connection(
        "snowflake",
        ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"),
    )
    return connection.session()


@st.cache_resource
def get_app_context():
    """Return the database and schema hosting the Streamlit application."""
    session = get_session()

    row = session.sql(
        """
        SELECT
            CURRENT_DATABASE() AS DATABASE_NAME,
            CURRENT_SCHEMA() AS SCHEMA_NAME
        """
    ).collect()[0]

    return row["DATABASE_NAME"], row["SCHEMA_NAME"]


DATABASE, MARTS_SCHEMA = get_app_context()

MARTS = f"{DATABASE}.{MARTS_SCHEMA}"

FCT_LISTING_SNAPSHOT = f"{MARTS}.FCT_LISTING_SNAPSHOT"
REF_LYON_ARRONDISSEMENTS = f"{MARTS}.REF_LYON_ARRONDISSEMENTS"
