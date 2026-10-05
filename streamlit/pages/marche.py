import pandas as pd
import streamlit as st

from ui.components import (
    insight_box,
    kpi_grid,
    note,
    page_header,
    section_header,
    transition_grid,
)
from ui.formatters import (
    format_date_fr,
    format_integer,
    format_percent,
    format_signed_integer,
    format_signed_percent,
)

from ui.config import MARTS, get_session
from ui.sidebar import render_sidebar

from ui.styles import apply_global_styles

apply_global_styles()

# ============================================================
# Snowflake connection
# ============================================================

session = get_session()

# ============================================================
# Data loading
# ============================================================

@st.cache_data(ttl=3600)
def load_market_data():

    market = session.sql(f"""
        SELECT *
        FROM {MARTS}.MART_MARKET_SNAPSHOT
        ORDER BY SNAPSHOT_DATE
    """).to_pandas()

    transitions = session.sql(f"""
        SELECT *
        FROM {MARTS}.MART_MARKET_TRANSITION
        ORDER BY SNAPSHOT_DATE
    """).to_pandas()

    for dataframe in [market, transitions]:
        dataframe.columns = dataframe.columns.str.lower()

    market["snapshot_date"] = pd.to_datetime(
        market["snapshot_date"]
    ).dt.date

    transitions["snapshot_date"] = pd.to_datetime(
        transitions["snapshot_date"]
    ).dt.date

    transitions["previous_snapshot_date"] = pd.to_datetime(
        transitions["previous_snapshot_date"]
    ).dt.date

    return market, transitions

market, transitions = load_market_data()

# ============================================================
# Snapshot selection
# ============================================================

snapshot_dates = sorted(
    market["snapshot_date"]
    .dropna()
    .unique()
    .tolist()
)

selected_snapshot = render_sidebar(
    snapshot_dates=snapshot_dates,
)

selected_snapshot = pd.to_datetime(
    selected_snapshot
).date()


current_market_df = market[
    market["snapshot_date"] == selected_snapshot
]

if current_market_df.empty:
    st.error(
        "Aucune donnée de marché n'est disponible "
        "pour l'observation sélectionnée."
    )
    st.stop()

current_market = current_market_df.iloc[0]

transition_df = transitions[
    transitions["snapshot_date"] == selected_snapshot
]

current_transition = (
    transition_df.iloc[0]
    if not transition_df.empty
    else None
)

# ============================================================
# Current metrics
# ============================================================

listing_count = int(
    current_market["listing_count"]
)

entire_home_count = int(
    current_market["entire_home_listing_count"]
)

private_room_count = int(
    current_market["private_room_listing_count"]
)

shared_room_count = int(
    current_market["shared_room_listing_count"]
)

entire_home_share = (
    100 * entire_home_count / listing_count
    if listing_count
    else None
)

private_room_share = (
    100 * private_room_count / listing_count
    if listing_count
    else None
)

shared_room_share = (
    100 * shared_room_count / listing_count
    if listing_count
    else None
)

# ============================================================
# Header
# ============================================================

page_header(
    title="Marché",
    icon="📈",
    subtitle=(
        "Évolution de l'offre Airbnb à Lyon et dynamique "
        "des annonces entre les observations historiques."
    ),
    badges=[
        "🇫🇷 Lyon, France",
        f"📅 {format_date_fr(selected_snapshot)}",
        f"🗂️ {len(snapshot_dates)} observations historiques",
    ],
)

# ============================================================
# Current market
# ============================================================

section_header(
    "Situation du marché",
    (
        "Composition de l'offre observée au "
        f"{format_date_fr(selected_snapshot)}."
    ),
)

market_kpis = [
    {
        "label": "Annonces observées",
        "value": format_integer(listing_count),
        "detail": (
            "Population totale de l'observation"
        ),
    },
    {
        "label": "Logements entiers",
        "value": format_integer(entire_home_count),
        "detail": (
            f"{format_percent(entire_home_share)} "
            "des annonces observées"
        ),
    },
    {
        "label": "Chambres privées",
        "value": format_integer(private_room_count),
        "detail": (
            f"{format_percent(private_room_share)} "
            "des annonces observées"
        ),
    },
    {
        "label": "Chambres partagées",
        "value": format_integer(shared_room_count),
        "detail": (
            f"{format_percent(shared_room_share)} "
            "des annonces observées"
        ),
    },
]

kpi_grid(
    market_kpis,
    columns=2,
)

# ============================================================
# Historical supply
# ============================================================

st.divider()

section_header(
    "Évolution de l'offre",
    (
        "Nombre d'annonces observées et composition principale "
        "du marché à chaque observation."
    ),
)

chart_data = market[
    [
        "snapshot_date",
        "listing_count",
        "entire_home_listing_count",
        "private_room_listing_count",
    ]
].copy()

chart_data = chart_data.sort_values(
    "snapshot_date"
).reset_index(drop=True)

chart_data["snapshot_label"] = (
    chart_data["snapshot_date"]
    .apply(format_date_fr)
)

snapshot_order = chart_data["snapshot_label"].tolist()

chart_data["snapshot_label"] = pd.Categorical(
    chart_data["snapshot_label"],
    categories=snapshot_order,
    ordered=True,
)

chart_data = chart_data.rename(
    columns={
        "listing_count": "Toutes les annonces",
        "entire_home_listing_count": "Logements entiers",
        "private_room_listing_count": "Chambres privées",
    }
)

st.line_chart(
    chart_data,
    x="snapshot_label",
    y=[
        "Toutes les annonces",
        "Logements entiers",
        "Chambres privées",
    ],
    x_label="Date d'observation",
    y_label="Nombre d'annonces",
)

note(
    "Chaque point correspond à une observation Inside Airbnb. "
    "La variation entre deux points représente une variation de "
    "population observée et non nécessairement des créations ou "
    "suppressions définitives d'annonces."
)

# ============================================================
# Selected transition
# ============================================================

st.divider()

section_header(
    "Dynamique du marché",
    "Décomposition des mouvements depuis l'observation précédente.",
)


if current_transition is None:

    st.info(
        "La date sélectionnée correspond à la première observation "
        "disponible. Aucune transition antérieure ne peut être calculée."
    )

else:

    previous_date = current_transition[
        "previous_snapshot_date"
    ]

    previous_listing_count = int(
        current_transition["previous_listing_count"]
    )

    current_listing_count = int(
        current_transition["current_listing_count"]
    )

    retained_count = int(
        current_transition["retained_listing_count"]
    )

    disappeared_count = int(
        current_transition["disappeared_listing_count"]
    )

    newly_observed_count = int(
        current_transition["newly_observed_listing_count"]
    )

    returned_count = int(
        current_transition["returned_after_gap_listing_count"]
    )

    net_change = int(
        current_transition["net_listing_change"]
    )

    net_change_pct = float(
        current_transition["net_listing_change_pct"]
    )

    retention_rate = float(
        current_transition["retention_rate_pct"]
    )

    disappearance_rate = float(
        current_transition["disappearance_rate_pct"]
    )

    newly_observed_share = float(
        current_transition["newly_observed_share_pct"]
    )

    returned_share = float(
        current_transition["returned_after_gap_share_pct"]
    )

    # --------------------------------------------------------
    # Analytical summary
    # --------------------------------------------------------

    if returned_count > newly_observed_count:

        interpretation = (
            f"Entre le {format_date_fr(previous_date)} et le "
            f"{format_date_fr(selected_snapshot)}, le marché observé "
            f"évolue de {format_signed_integer(net_change)} annonces. "
            f"Les retours après absence ({format_integer(returned_count)}) "
            f"sont plus nombreux que les premières apparitions "
            f"({format_integer(newly_observed_count)})."
        )

    else:

        interpretation = (
            f"Entre le {format_date_fr(previous_date)} et le "
            f"{format_date_fr(selected_snapshot)}, le marché observé "
            f"évolue de {format_signed_integer(net_change)} annonces. "
            f"Les premières apparitions "
            f"({format_integer(newly_observed_count)}) sont au moins "
            f"aussi nombreuses que les retours après absence "
            f"({format_integer(returned_count)})."
        )

    insight_box(
        (
            "Variation nette : "
            f"{format_signed_integer(net_change)} annonces "
            f"({format_signed_percent(net_change_pct)})"
        ),
        interpretation,
    )

    # --------------------------------------------------------
    # Movement decomposition
    # --------------------------------------------------------

    
    transition_items = [
        {
            "label": "Conservées",
            "value": format_integer(retained_count),
            "detail": (
                f"{format_percent(retention_rate)} "
                "des annonces précédentes"
            ),
        },
        {
            "label": "Disparues",
            "value": format_integer(disappeared_count),
            "detail": (
                f"{format_percent(disappearance_rate)} "
                "des annonces précédentes"
            ),
        },
        {
            "label": "Nouvellement observées",
            "value": format_integer(newly_observed_count),
            "detail": (
                f"{format_percent(newly_observed_share)} "
                "de la population actuelle"
            ),
        },
        {
            "label": "Retours après absence",
            "value": format_integer(returned_count),
            "detail": (
                f"{format_percent(returned_share)} "
                "de la population actuelle"
            ),
        },
    ]

    transition_grid(
        transition_items,
        columns=2,
    )

    st.divider() 
      
    # --------------------------------------------------------
    # Reconciliation
    # --------------------------------------------------------

    st.write("")

    section_header(
        "Solde de la transition",
        (
            f"Passage du {format_date_fr(previous_date)} "
            f"au {format_date_fr(selected_snapshot)} · "
            f"{int(current_transition['days_between_snapshots'])} jours."
        ),
    )

    balance_items = [
        {
            "label": "Observation précédente",
            "value": format_integer(previous_listing_count),
            "detail": format_date_fr(previous_date),
        },
        {
            "label": "Variation nette",
            "value": format_signed_integer(net_change),
            "detail": format_signed_percent(net_change_pct),
        },
        {
            "label": "Observation actuelle",
            "value": format_integer(current_listing_count),
            "detail": format_date_fr(selected_snapshot),
        },
    ]

    kpi_grid(
        balance_items,
        columns=3,
    )

# ============================================================
# Transition history
# ============================================================

st.divider()

section_header(
    "Historique des mouvements",
    (
        "Décomposition des annonces conservées, disparues, "
        "nouvellement observées et revenues après absence."
    ),
)

if transitions.empty:

    st.info(
        "Aucune transition historique n'est disponible."
    )

else:

    transition_chart = transitions[
        [
            "snapshot_date",
            "retained_listing_count",
            "disappeared_listing_count",
            "newly_observed_listing_count",
            "returned_after_gap_listing_count",
        ]
    ].copy()

    transition_chart = transition_chart.sort_values(
        "snapshot_date"
    ).reset_index(drop=True)

    transition_chart["snapshot_label"] = (
        transition_chart["snapshot_date"]
        .apply(format_date_fr)
    )

    snapshot_order = (
        transition_chart["snapshot_label"]
        .tolist()
    )

    transition_chart["snapshot_label"] = pd.Categorical(
        transition_chart["snapshot_label"],
        categories=snapshot_order,
        ordered=True,
    )

    transition_chart = transition_chart.rename(
        columns={
            "retained_listing_count": "Conservées",
            "disappeared_listing_count": "Disparues",
            "newly_observed_listing_count": "Nouvellement observées",
            "returned_after_gap_listing_count": "Retours après absence",
        }
    )

    st.bar_chart(
        transition_chart,
        x="snapshot_label",
        y=[
            "Conservées",
            "Disparues",
            "Nouvellement observées",
            "Retours après absence",
        ],
        x_label="Observation actuelle",
        y_label="Nombre d'annonces",
        stack=False,
    )

    note(
        "Chaque groupe de barres décrit la transition conduisant "
        "à l'observation indiquée sur l'axe horizontal."
    )

# ============================================================
# Methodological interpretation
# ============================================================

st.divider()

with st.expander(
    "Comment interpréter les mouvements ?"
):

    st.markdown(
        """
Les mouvements sont reconstruits à partir de la présence d'une
annonce dans les différents observations historiques.

- **Conservée** : présente dans les deux observations consécutives.
- **Disparue** : présente précédemment mais absente actuellement.
- **Nouvellement observée** : première apparition dans l'historique disponible.
- **Retour après absence** : déjà observée auparavant, absente du snapshot
  précédent puis de nouveau présente.

Une disparition ne constitue donc pas nécessairement une suppression
définitive de l'annonce Airbnb.

Les taux de **rétention** et de **disparition** sont calculés par rapport
à la population précédente. Les parts des annonces **nouvellement
observées** et **revenues après absence** sont calculées par rapport à
la population actuelle.
        """
    )