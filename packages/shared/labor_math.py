"""人工成本核算 · 纯函数（非 engine）。"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def decimal_hours(value: str | float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def labor_cost(hours_man: Decimal, rate_per_hour: Decimal) -> Decimal:
    return (hours_man * rate_per_hour).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def variance_pct(planned: Decimal, actual: Decimal) -> Decimal | None:
    if planned <= 0:
        return None
    return ((actual - planned) / planned * Decimal("100")).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
