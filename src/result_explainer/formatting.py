"""How result values are displayed. Facts, prompts and CLI output all use these strings."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

DECIMALS = {"count": 0, "currency": 2, "percent": 1, "number": 1}
NULL_DISPLAY = "n/a"


def round_half_up(value: object, decimals: int) -> Decimal:
    """Round the way people do (7.45 -> 7.5), not banker's rounding."""
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def numeric_value(value: object, kind: str) -> Decimal | None:
    """The value exactly as displayed, used to match numbers written in explanations.

    Text labels have no numeric value, except plain integers such as an order id.
    """
    if value is None:
        return None
    if kind == "label":
        text = str(value)
        return Decimal(text) if text.isdigit() else None
    return round_half_up(value, DECIMALS[kind])


def format_value(value: object, kind: str) -> str:
    if value is None:
        return NULL_DISPLAY
    if kind == "label":
        return str(value)
    amount = round_half_up(value, DECIMALS[kind])
    text = f"{abs(amount):,.{DECIMALS[kind]}f}"
    sign = "-" if amount < 0 else ""
    if kind == "currency":
        return f"{sign}${text}"
    if kind == "percent":
        return f"{sign}{text}%"
    return sign + text
