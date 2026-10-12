from html import escape

import streamlit as st

def page_header(
    title: str,
    subtitle: str | None = None,
    icon: str | None = None,
    badges: list[str] | None = None,
) -> None:
    """Afficher l'en-tête commun des pages."""

    icon_html = f"{escape(icon)} " if icon else ""

    subtitle_html = ""
    if subtitle:
        subtitle_html = (
            f'<div class="ia-page-subtitle">'
            f'{escape(subtitle)}'
            f'</div>'
        )

    badges_html = ""
    if badges:
        badges_content = "".join(
            f'<span class="ia-context-badge">{escape(str(badge))}</span>'
            for badge in badges
        )

        badges_html = (
            f'<div class="ia-context-row">'
            f'{badges_content}'
            f'</div>'
        )

    st.markdown(
        f"""
        <div class="ia-page-header">
            <div class="ia-page-title">
                {icon_html}{escape(title)}
            </div>
            {subtitle_html}
            {badges_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(
    title: str,
    description: str | None = None,
) -> None:
    """Afficher un titre de section uniforme et sa description facultative."""

    description_html = ""

    if description:
        description_html = (
            f'<div class="ia-section-description">'
            f'{escape(description)}'
            f'</div>'
        )

    st.markdown(
        f"""
        <div class="ia-section-header">
            <div class="ia-section-title">
                {escape(title)}
            </div>
            {description_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(
    label: str,
    value: str,
    detail: str | None = None,
) -> None:
    """Afficher une carte d'indicateur principal."""

    detail_html = ""

    if detail:
        detail_html = (
            f'<div class="ia-kpi-detail">'
            f'{escape(detail)}'
            f'</div>'
        )

    st.markdown(
        f"""
        <div class="ia-kpi-card">
            <div class="ia-kpi-label">
                {escape(label)}
            </div>
            <div class="ia-kpi-value">
                {escape(value)}
            </div>
            {detail_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def transition_card(
    label: str,
    value: str,
    detail: str | None = None,
) -> None:
    """Afficher une carte compacte de transition du marché."""

    detail_html = ""

    if detail:
        detail_html = (
            f'<div class="ia-transition-detail">'
            f'{escape(detail)}'
            f'</div>'
        )

    st.markdown(
        f"""
        <div class="ia-transition-card">
            <div class="ia-transition-label">
                {escape(label)}
            </div>
            <div class="ia-transition-value">
                {escape(value)}
            </div>
            {detail_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def insight_box(
    title: str,
    text: str,
) -> None:
    """Afficher un encadré d'interprétation analytique."""

    st.markdown(
        f"""
        <div class="ia-insight">
            <div class="ia-insight-title">
                {escape(title)}
            </div>
            <div class="ia-insight-text">
                {escape(text)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def note(text: str) -> None:
    """Afficher une note méthodologique discrète."""

    st.markdown(
        f"""
        <div class="ia-note">
            {escape(text)}
        </div>
        """,
        unsafe_allow_html=True,
    )

def kpi_grid(
    items: list[dict],
    columns: int = 2,
) -> None:
    """Afficher les cartes d'indicateurs dans une grille adaptative."""

    for start in range(0, len(items), columns):
        row_items = items[start:start + columns]
        cols = st.columns(columns)

        for index, item in enumerate(row_items):
            with cols[index]:
                kpi_card(
                    label=item["label"],
                    value=item["value"],
                    detail=item.get("detail"),
                )

        if start + columns < len(items):
            st.write("")


def transition_grid(
    items: list[dict],
    columns: int = 2,
) -> None:
    """Afficher les cartes de transition dans une grille adaptative."""

    for start in range(0, len(items), columns):
        row_items = items[start:start + columns]
        cols = st.columns(columns)

        for index, item in enumerate(row_items):
            with cols[index]:
                transition_card(
                    label=item["label"],
                    value=item["value"],
                    detail=item.get("detail"),
                )

        if start + columns < len(items):
            st.write("")