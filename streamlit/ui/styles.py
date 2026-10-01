import streamlit as st

GLOBAL_CSS = """
<style>

/* ============================================================
   Global layout
   ============================================================ */

.block-container {
    max-width: 1500px;
    padding-top: 2.2rem;
    padding-bottom: 4rem;
}

/* ============================================================
   Page header
   ============================================================ */

.ia-page-header {
    margin-bottom: 1.8rem;
}

.ia-page-title {
    font-size: 2.35rem;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -0.035em;
    margin: 0;
}

.ia-page-subtitle {
    margin-top: 0.55rem;
    font-size: 1rem;
    color: #6b7280;
    line-height: 1.55;
}

.ia-context-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1rem;
}

.ia-context-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.65rem;
    border-radius: 999px;
    background: rgba(120, 120, 120, 0.08);
    border: 1px solid rgba(120, 120, 120, 0.16);
    font-size: 0.82rem;
    line-height: 1;
}

/* ============================================================
   Sidebar controls
   ============================================================ */

/* Selectbox container */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    min-height: 44px;
    border-radius: 10px;
    border-color: rgba(120, 120, 120, 0.20);
    background-color: #FFFFFF;
    box-shadow: none;
    transition:
        border-color 0.15s ease,
        box-shadow 0.15s ease;
}

/* Selectbox hover */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover {
    border-color: rgba(59, 130, 246, 0.55);
}

/* Selectbox focus */
section[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within {
    border-color: #3B82F6;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.10);
}

/* Selected value */
section[data-testid="stSidebar"] div[data-baseweb="select"] span {
    font-size: 0.88rem;
}

/* Selectbox label */
section[data-testid="stSidebar"] div[data-testid="stSelectbox"] label {
    font-size: 0.82rem;
    font-weight: 500;
    margin-bottom: 0.25rem;
}

/* Sidebar divider */
section[data-testid="stSidebar"] hr {
    border-color: rgba(120, 120, 120, 0.14);
}

/* ============================================================
   Sections
   ============================================================ */

.ia-section-header {
    margin-top: 0.3rem;
    margin-bottom: 1.15rem;
}

.ia-section-title {
    font-size: 1.55rem;
    font-weight: 650;
    letter-spacing: -0.02em;
    margin: 0;
}

.ia-section-description {
    color: #6b7280;
    margin-top: 0.35rem;
    font-size: 0.92rem;
    line-height: 1.5;
}

/* ============================================================
   KPI cards
   ============================================================ */

.ia-kpi-card {
    min-height: 138px;
    height: 100%;
    padding: 1.15rem 1.2rem;
    border: 1px solid rgba(120, 120, 120, 0.18);
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.015);
}

.ia-kpi-label {
    color: #6b7280;
    font-size: 0.83rem;
    font-weight: 500;
    margin-bottom: 0.45rem;
}

.ia-kpi-value {
    font-size: 1.85rem;
    font-weight: 650;
    letter-spacing: -0.025em;
    line-height: 1.15;
}

.ia-kpi-detail {
    margin-top: 0.55rem;
    color: #6b7280;
    font-size: 0.79rem;
    line-height: 1.35;
}

/* ============================================================
   Insight / information boxes
   ============================================================ */

.ia-insight {
    padding: 1rem 1.15rem;
    border-radius: 12px;
    border-left: 4px solid #3b82f6;
    background: rgba(59, 130, 246, 0.07);
    margin: 0.6rem 0 1.4rem 0;
}

.ia-insight-title {
    font-weight: 650;
    margin-bottom: 0.25rem;
}

.ia-insight-text {
    color: #6b7280;
    font-size: 0.9rem;
    line-height: 1.5;
}

/* ============================================================
   Transition / movement summary
   ============================================================ */

.ia-transition-card {
    padding: 1rem 1.15rem;
    border: 1px solid rgba(120, 120, 120, 0.18);
    border-radius: 12px;
    height: 100%;
}

.ia-transition-label {
    color: #6b7280;
    font-size: 0.82rem;
    margin-bottom: 0.35rem;
}

.ia-transition-value {
    font-size: 1.45rem;
    font-weight: 650;
}

.ia-transition-detail {
    color: #6b7280;
    font-size: 0.78rem;
    margin-top: 0.35rem;
}

/* ============================================================
   Small notes
   ============================================================ */

.ia-note {
    color: #6b7280;
    font-size: 0.82rem;
    line-height: 1.5;
    margin-top: 0.6rem;
}

/* ============================================================
   Cards sizing
   ============================================================ */

.ia-kpi-card,
.ia-transition-card {
    min-width: 0;
}


/* ============================================================
   Tablet / compact desktop
   ============================================================ */

@media (max-width: 1100px) {

    .block-container {
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }

    .ia-page-title {
        font-size: 2rem;
    }

    .ia-kpi-card {
        min-height: 125px;
    }
}


/* ============================================================
   Mobile
   ============================================================ */

@media (max-width: 700px) {

    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1.3rem;
    }

    .ia-page-title {
        font-size: 1.75rem;
    }

    .ia-page-subtitle {
        font-size: 0.9rem;
    }

    .ia-section-title {
        font-size: 1.3rem;
    }

    .ia-kpi-card,
    .ia-transition-card {
        min-height: auto;
    }

    .ia-kpi-value {
        font-size: 1.65rem;
    }
}

</style>
"""


def apply_global_styles() -> None:
    """Apply the common visual system to the current Streamlit page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)