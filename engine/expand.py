"""需求展开：订单 → 成品工单（BR-02）。半成品展开见阶段 2。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Sequence

from engine.models import Item, Order, Sph, UomConvert, Wo, WoStatus, WoType
from engine.uom import to_board


def _ceil_board(qty: Decimal) -> int:
    return int(qty.to_integral_value(rounding=ROUND_CEILING))


def expand_order(
    order: Order,
    item: Item,
    converts: Sequence[UomConvert],
    today: date,
    sph: Sph | None = None,
    seq: int = 1,
) -> Wo | None:
    """订单 → 成品 Wo。computable=false 的品项跳过，返回 None。"""
    if not item.computable:
        return None

    qty_board = to_board(order.qty_order, order.unit, converts)
    qty_board_plan = _ceil_board(qty_board * (Decimal(1) + item.loss_rate))
    ready = order.ready_date or today
    crew_plan = sph.crew_std if sph is not None else 1
    return Wo(
        wo_no=f"WO-{order.order_no}-{seq}",
        wo_type=WoType.FINISHED,
        source_order_no=order.order_no,
        item_code=item.item_code,
        group_code=item.group_code,
        dept=item.dept,
        qty_order=order.qty_order,
        qty_board_plan=qty_board_plan,
        due_date=order.due_date,
        earliest_start=max(today, ready),
        crew_plan=crew_plan,
        status=WoStatus.DRAFT,
    )


def expand_semi(*_args, **_kwargs):
    """BR-30~33：阶段 2 实现。"""
    raise NotImplementedError("expand_semi: Phase 2 (BR-30~33)")
