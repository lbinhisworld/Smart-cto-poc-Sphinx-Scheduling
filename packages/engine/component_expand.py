"""多行 BOM 展开半成品工单（BR-37~39）。"""

from __future__ import annotations

from datetime import date, timedelta

from engine.bom import gross_board_for_line
from engine.kit_pool import KitSnapshot
from engine.models import (
    BomLine,
    ComponentRole,
    Item,
    KitLineResult,
    Order,
    Sph,
    Wo,
    WoStatus,
    WoType,
)


def expand_semi_from_line(
    finished_wo: Wo,
    order: Order,
    line: BomLine,
    finished_item: Item,
    semi_item: Item,
    pool: KitSnapshot,
    today: date,
    sph: Sph | None,
    *,
    multi_semi_wo_suffix: bool = False,
) -> tuple[Wo | None, KitLineResult]:
    gross = gross_board_for_line(order, line, finished_item)
    from_stock, net = pool.consume(
        order_no=order.order_no,
        component_item_code=line.component_item_code,
        gross_board=gross,
        line_no=line.line_no,
    )
    line_result = KitLineResult(
        line_no=line.line_no,
        component_item_code=line.component_item_code,
        component_role=line.component_role,
        gross_board=gross,
        from_stock=from_stock,
        net_wo_board=net,
        shortage_board=0,
    )
    if net <= 0:
        line_result.ready_date = today
        return None, line_result
    if finished_wo.plan_start is None:
        return None, line_result

    semi_due = finished_wo.plan_start - timedelta(days=line.lead_time_days)
    crew_plan = sph.crew_std if sph is not None else 1
    wo_suffix = f"-SEMI-{line.line_no}" if multi_semi_wo_suffix else "-SEMI"
    wo = Wo(
        wo_no=f"WO-{order.order_no}{wo_suffix}",
        wo_type=WoType.SEMI,
        source_order_no=order.order_no,
        item_code=semi_item.item_code,
        group_code=semi_item.group_code,
        dept=semi_item.dept,
        qty_order=order.qty_order,
        qty_board_plan=net,
        due_date=semi_due,
        earliest_start=today,
        crew_plan=crew_plan,
        status=WoStatus.DRAFT,
        parent_wo_no=finished_wo.wo_no,
        bom_line_no=line.line_no,
    )
    return wo, line_result


def consume_purchased_line(
    order: Order,
    line: BomLine,
    finished_item: Item,
    pool: KitSnapshot,
    today: date,
) -> KitLineResult:
    gross = gross_board_for_line(order, line, finished_item)
    from_stock, net = pool.consume(
        order_no=order.order_no,
        component_item_code=line.component_item_code,
        gross_board=gross,
        line_no=line.line_no,
    )
    shortage = net
    ready = today if shortage <= 0 else None
    return KitLineResult(
        line_no=line.line_no,
        component_item_code=line.component_item_code,
        component_role=ComponentRole.PURCHASED,
        gross_board=gross,
        from_stock=from_stock,
        net_wo_board=0,
        shortage_board=shortage,
        ready_date=ready,
    )
