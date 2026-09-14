"""单位换算链（BR-01 / BR-03 / BR-04 / BR-05）。

禁止硬编码 box→board 等魔法数字；必须沿 md_uom_convert 邻接边走。
POC 仅 PCS / BOARD / BOX 参与计算。
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal
from typing import Sequence

from engine.errors import UomConvertError
from engine.models import Uom, UomConvert

COMPUTABLE_UOMS = frozenset({Uom.PCS, Uom.BOARD, Uom.BOX})


def convert_qty(
    qty: Decimal,
    from_uom: Uom,
    to_uom: Uom,
    converts: Sequence[UomConvert],
) -> Decimal:
    """沿换算链把 qty 从 from_uom 换到 to_uom（BR-03）。

    正向边乘 factor，反向边除 factor。同单位直接返回。
    """
    qty = Decimal(qty)
    if from_uom == to_uom:
        return qty

    graph: dict[Uom, list[tuple[Uom, Decimal]]] = {}
    for row in converts:
        graph.setdefault(row.from_uom, []).append((row.to_uom, row.factor))
        graph.setdefault(row.to_uom, []).append((row.from_uom, Decimal(1) / row.factor))

    queue: deque[tuple[Uom, Decimal]] = deque([(from_uom, qty)])
    seen: set[Uom] = {from_uom}
    while queue:
        current, value = queue.popleft()
        for nxt, factor in graph.get(current, []):
            if nxt in seen:
                continue
            new_value = value * factor
            if nxt == to_uom:
                return new_value
            seen.add(nxt)
            queue.append((nxt, new_value))

    raise UomConvertError(f"无换算路径 {from_uom.value} → {to_uom.value}")


def to_board(qty: Decimal, from_uom: Uom, converts: Sequence[UomConvert]) -> Decimal:
    """任意单位数量归一到「版」（BR-01）。"""
    return convert_qty(qty, from_uom, Uom.BOARD, converts)


def sph_to_board_per_hour(sph_value: Decimal, sph_uom: Uom, converts: Sequence[UomConvert]) -> Decimal:
    """SPH 换算到 版/小时（BR-04）。"""
    return convert_qty(sph_value, sph_uom, Uom.BOARD, converts)
