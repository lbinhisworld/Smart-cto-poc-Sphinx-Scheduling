"""需求展开：订单 → 成品 / 半成品工单（BR-02, BR-30~33）。"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Sequence

from engine.models import Item, ItemRoute, Order, Sph, UomConvert, Wo, WoStatus, WoType
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


def gross_semi_board(finished_wo: Wo, route: ItemRoute, finished_item: Item) -> int:
    """BR-31：毛需求（版）。"""
    assert route.semi_board_per_box is not None
    raw = finished_wo.qty_order * route.semi_board_per_box * (Decimal(1) + finished_item.loss_rate)
    return _ceil_board(raw)


def expand_semi(
    finished_wo: Wo,
    route: ItemRoute,
    finished_item: Item,
    semi_item: Item,
    stock: dict[str, Decimal],
    today: date,
    sph: Sph | None = None,
) -> Wo | None:
    """成品排定 plan_start 后展开半成品（BR-30~33）。"""
    if not route.needs_semi or route.semi_item_code is None:
        return None
    if finished_wo.plan_start is None:
        return None

    gross = gross_semi_board(finished_wo, route, finished_item)
    available = stock.get(route.semi_item_code, Decimal(0))
    net = max(0, gross - int(available))
    if net == 0:
        return None

    semi_due = finished_wo.plan_start - timedelta(days=route.lead_time_days)
    crew_plan = sph.crew_std if sph is not None else 1

    return Wo(
        wo_no=f"WO-{finished_wo.source_order_no}-SEMI",
        wo_type=WoType.SEMI,
        source_order_no=finished_wo.source_order_no,
        item_code=semi_item.item_code,
        group_code=semi_item.group_code,
        dept=semi_item.dept,
        qty_order=finished_wo.qty_order,
        qty_board_plan=net,
        due_date=semi_due,
        earliest_start=today,
        crew_plan=crew_plan,
        status=WoStatus.DRAFT,
        parent_wo_no=finished_wo.wo_no,
    )
