
import streamlit as st


st.set_page_config(
    page_title="Inside Airbnb Analytics",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


pages = {
    "Analyse": [
        st.Page(
            "pages/overview.py",
            title="Vue d'ensemble",
            icon="🏠",
            default=True,
        ),
        st.Page(
            "pages/marche.py",
            title="Marché",
            icon="📈",
        ),
        st.Page(
            "pages/quartiers.py",
            title="Quartiers",
            icon="🗺️",
        ),
        st.Page(
            "pages/cartographie.py",
            title="Cartographie",
            icon="📍",
        ),
        st.Page(
            "pages/prix.py",
            title="Prix",
            icon="💶",
        ),
        st.Page(
            "pages/disponibilite.py",
            title="Disponibilité",
            icon="📅",
        ),
        st.Page(
            "pages/hotes.py",
            title="Hôtes",
            icon="👥",
        ),
        st.Page(
            "pages/comparateur.py",
            title="Comparateur temporel",
            icon="🔄",
        ),
    ],
    "Informations": [
        st.Page(
            "pages/methodologie.py",
            title="Méthodologie",
            icon="ℹ️",
        ),
    ],
}


navigation = st.navigation(pages)
navigation.run()