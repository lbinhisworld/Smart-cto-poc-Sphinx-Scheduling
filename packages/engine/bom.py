"""BOM 行用量 → 版（BR-37 / BR-01）。"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

from engine.models import BomLine, Item, Order, Uom


def _ceil_board(qty: Decimal) -> int:
    return int(qty.to_integral_value(rounding=ROUND_CEILING))


def gross_board_for_line(
    order: Order,
    line: BomLine,
    finished_item: Item,
) -> int:
    """子件毛需求（版）。"""
    scrap = line.scrap_rate if line.scrap_rate is not None else finished_item.loss_rate
    if line.qty_basis_uom == Uom.BOX:
        raw = order.qty_order * line.qty_per_parent * (Decimal(1) + scrap)
    else:
        raw = line.qty_per_parent * (Decimal(1) + scrap)
    return _ceil_board(raw)
