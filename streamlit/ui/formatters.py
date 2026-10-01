from datetime import date, datetime

import pandas as pd


# ============================================================
# Internal helpers
# ============================================================

def _is_missing(value) -> bool:
    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _format_number_fr(value: float, decimals: int) -> str:
    formatted = f"{float(value):,.{decimals}f}"

    return (
        formatted
        .replace(",", "\u202f")
        .replace(".", ",")
    )


# ============================================================
# Numbers
# ============================================================

def format_integer(value, na: str = "N/D") -> str:
    if _is_missing(value):
        return na

    return f"{int(round(float(value))):,}".replace(",", "\u202f")


def format_decimal(
    value,
    decimals: int = 1,
    na: str = "N/D",
) -> str:
    if _is_missing(value):
        return na

    return _format_number_fr(value, decimals)


def format_percent(
    value,
    decimals: int = 1,
    na: str = "N/D",
) -> str:
    if _is_missing(value):
        return na

    return f"{_format_number_fr(value, decimals)} %"


def format_currency(
    value,
    decimals: int = 0,
    na: str = "N/D",
) -> str:
    if _is_missing(value):
        return na

    return f"{_format_number_fr(value, decimals)} €"


# ============================================================
# Signed values / temporal deltas
# ============================================================

def format_signed_integer(
    value,
    na: str | None = None,
) -> str | None:
    if _is_missing(value):
        return na

    numeric_value = int(round(float(value)))
    sign = "+" if numeric_value > 0 else ""

    return (
        f"{sign}{numeric_value:,}"
        .replace(",", "\u202f")
    )


def format_signed_decimal(
    value,
    decimals: int = 1,
    suffix: str = "",
    na: str | None = None,
) -> str | None:
    if _is_missing(value):
        return na

    numeric_value = float(value)
    sign = "+" if numeric_value > 0 else ""

    return (
        f"{sign}{_format_number_fr(numeric_value, decimals)}"
        f"{suffix}"
    )


def format_signed_percent(
    value,
    decimals: int = 1,
    na: str | None = None,
) -> str | None:
    return format_signed_decimal(
        value,
        decimals=decimals,
        suffix=" %",
        na=na,
    )


def format_signed_currency(
    value,
    decimals: int = 0,
    na: str | None = None,
) -> str | None:
    return format_signed_decimal(
        value,
        decimals=decimals,
        suffix=" €",
        na=na,
    )


# ============================================================
# Dates
# ============================================================

def format_date_fr(
    value,
    na: str = "N/D",
) -> str:
    if _is_missing(value):
        return na

    parsed = pd.to_datetime(value)

    return parsed.strftime("%d/%m/%Y")


def format_month_fr(
    value,
    na: str = "N/D",
) -> str:
    if _is_missing(value):
        return na

    parsed = pd.to_datetime(value)

    months = {
        1: "janv.",
        2: "févr.",
        3: "mars",
        4: "avr.",
        5: "mai",
        6: "juin",
        7: "juil.",
        8: "août",
        9: "sept.",
        10: "oct.",
        11: "nov.",
        12: "déc.",
    }

    return f"{months[parsed.month]} {parsed.year}"


def format_date_short_fr(
    value,
    na: str = "N/D",
) -> str:
    if _is_missing(value):
        return na

    parsed = pd.to_datetime(value)

    months = {
        1: "janv.",
        2: "févr.",
        3: "mars",
        4: "avr.",
        5: "mai",
        6: "juin",
        7: "juil.",
        8: "août",
        9: "sept.",
        10: "oct.",
        11: "nov.",
        12: "déc.",
    }

    return f"{parsed.day} {months[parsed.month]} {parsed.year}"


# ============================================================
# Generic helpers
# ============================================================

def safe_ratio(
    numerator,
    denominator,
    multiplier: float = 100.0,
):
    if (
        _is_missing(numerator)
        or _is_missing(denominator)
        or float(denominator) == 0
    ):
        return None

    return (
        float(numerator)
        / float(denominator)
        * multiplier
    )