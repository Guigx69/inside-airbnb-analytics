import streamlit as st

from ui.components import (
    insight_box,
    kpi_card,
    page_header,
    section_header,
    transition_card,
)
from ui.styles import apply_global_styles


# ============================================================
# Global styles
# ============================================================

apply_global_styles()


# ============================================================
# Page header
# ============================================================

page_header(
    title="Inside Airbnb Analytics",
    icon="🏙️",
    subtitle="Observatoire du marché de la location courte durée à Lyon",
    badges=[
        "🇫🇷 Lyon, France",
        "📅 22 juin 2026",
        "🗂️ 4 observations historiques",
    ],
)


# ============================================================
# Main KPIs
# ============================================================

section_header(
    "Marché en un coup d'œil",
    "Principaux indicateurs du marché pour l'observation sélectionnée.",
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    kpi_card(
        "Annonces observées",
        "9\u202f317",
        "Marché observé",
    )

with c2:
    kpi_card(
        "Prix médian",
        "103,68 €",
        "Couverture tarifaire : 58,2 %",
    )

with c3:
    kpi_card(
        "Disponibilité à 30 jours",
        "34,0 %",
        "Disponibilité déclarée",
    )

with c4:
    kpi_card(
        "Hôtes observés",
        "6\u202f813",
        "1,37 annonce par hôte",
    )


# ============================================================
# Market dynamics
# ============================================================

st.divider()

section_header(
    "Dynamique du marché",
    "Décomposition de l'évolution depuis l'observation précédente.",
)

insight_box(
    "Variation nette : +4\u202f914 annonces",
    (
        "La forte hausse observée entre mars et juin provient "
        "principalement du retour d'annonces déjà présentes dans "
        "l'historique, et non de nouvelles annonces."
    ),
)

t1, t2, t3, t4 = st.columns(4)

with t1:
    transition_card(
        "Conservées",
        "4\u202f002",
        "Présentes aux deux observations",
    )

with t2:
    transition_card(
        "Nouvellement observées",
        "698",
        "Première apparition historique",
    )

with t3:
    transition_card(
        "Retours après absence",
        "4\u202f616",
        "Déjà observées auparavant",
    )

with t4:
    transition_card(
        "Disparues",
        "400",
        "Absentes de l'observation actuelle",
    )


# ============================================================
# Secondary KPIs
# ============================================================

st.divider()

section_header(
    "Structure du marché",
    "Exemple de second niveau d'indicateurs.",
)

s1, s2, s3, s4 = st.columns(4)

with s1:
    kpi_card(
        "Logements entiers",
        "80,2 %",
        "7\u202f476 annonces",
    )

with s2:
    kpi_card(
        "Hôtes multi-annonces",
        "11,2 %",
        "35,1 % des annonces contrôlées",
    )

with s3:
    kpi_card(
        "Superhosts",
        "17,9 %",
        "Part des hôtes observés",
    )

with s4:
    kpi_card(
        "Couverture tarifaire",
        "58,2 %",
        "5\u202f427 annonces avec prix",
    )


# ============================================================
# Interpretation example
# ============================================================

st.divider()

section_header(
    "Lecture analytique",
    "Exemple de mise en avant d'un enseignement important.",
)

insight_box(
    "Un marché fortement affecté par les retours d'annonces",
    (
        "Entre le 25 mars et le 22 juin 2026, 4\u202f616 annonces "
        "déjà observées historiquement réapparaissent après une absence. "
        "La variation brute de la population ne doit donc pas être "
        "interprétée comme une création équivalente de nouvelles annonces."
    ),
)


# ============================================================
# Footer
# ============================================================

st.divider()

st.caption(
    "Prototype du design system · "
    "Inside Airbnb Analytics · Snowflake + dbt + Streamlit"
)