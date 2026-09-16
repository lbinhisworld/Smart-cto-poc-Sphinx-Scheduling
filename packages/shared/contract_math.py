"""合同回款 · 纯函数。"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def money(value: str | float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def pending_amount(contract_amount: Decimal, received_total: Decimal) -> Decimal:
    diff = contract_amount - received_total
    return diff if diff > 0 else Decimal("0")


def receipt_would_exceed(contract_amount: Decimal, received_total: Decimal, new_amount: Decimal) -> bool:
    return received_total + new_amount > contract_amount + Decimal("0.001")
