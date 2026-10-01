import streamlit as st

from ui.formatters import format_date_fr

def render_sidebar(
    snapshot_dates: list,
):
    """Render the common sidebar and return the selected snapshot."""

    if not snapshot_dates:
        raise ValueError("snapshot_dates cannot be empty")

    st.sidebar.caption("OBSERVATION")

    selected_snapshot = st.sidebar.selectbox(
        "Snapshot",
        options=snapshot_dates,
        index=len(snapshot_dates) - 1,
        format_func=lambda value: f"📅 {format_date_fr(value)}",
        key="global_snapshot_date",
    )

    st.sidebar.divider()

    st.sidebar.markdown("**🇫🇷 Lyon, France**")

    st.sidebar.caption(
        f"Inside Airbnb · {len(snapshot_dates)} observations historiques"
    )

    return selected_snapshot