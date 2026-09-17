"""冲突检测 E1–E8（BR-50）与最快可交期（BR-47）。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from engine.calendar_util import add_natural_days, count_workdays_forward, next_workday
from engine.capacity import calendar_hours, detect_e8
from engine.expand import gross_semi_board
from engine.models import (
    Conflict,
    ConflictLv,
    ScheduleInput,
    ScheduleResult,
    Unplaced,
    Wo,
    WoType,
)


def detect_e6_e7(*_args, **_kwargs):
    raise NotImplementedError("E6/E7: SHOULD — Phase 6+ stub")


def due_conflict_suggest(ef: date | None, order_due: date | None) -> str:
    """最快日不晚于客户交期时不要建议改交期。"""
    if ef is None:
        return "REVIEW_WINDOW"
    if order_due is not None and ef <= order_due:
        return f"FEASIBLE:{ef.isoformat()}"
    return f"EARLIEST:{ef.isoformat()}"


def _md(d: date) -> str:
    return d.strftime("%m/%d").lstrip("0").replace("/0", "/")


def kit_semi_gap(result: ScheduleResult, wo: Wo) -> tuple[int, int, int] | None:
    for kit in result.kit_checks:
        if kit.order_no != wo.source_order_no:
            continue
        if wo.parent_wo_no and kit.finished_wo_no != wo.parent_wo_no:
            continue
        for line in kit.lines:
            if line.component_item_code == wo.item_code:
                return line.gross_board, line.from_stock, line.net_wo_board
    return None


def e2_conflict_message(
    order_no: str,
    due: date,
    ef: date | None,
    *,
    item_code: str = "",
    gross: int | None = None,
    from_stock: int | None = None,
    net: int | None = None,
) -> str:
    due_s = _md(due)
    sku = f" {item_code}" if item_code else ""
    gap = ""
    if gross is not None and from_stock is not None and net is not None:
        gap = (
            f"半成品{sku}库存不够：毛需求 {gross} 版，占库 {from_stock} 版，缺口 {net} 版，"
            f"必须开半成品工单补齐。"
        )
    if ef is None:
        return gap + "半成品来不及，无法满足成品开工"
    ef_s = _md(ef)
    if ef <= due:
        return (
            f"{gap}订单 {order_no} 客户要 {due_s}。"
            f"补产后按倒排试排，整单物理最快 {ef_s}，不晚于客户交期，交期本身够。"
            f"红灯是贴着交期往回填时半成品窗口不够，不是客户要得太早。"
        )
    return (
        f"{gap}订单 {order_no} 客户要 {due_s}。"
        f"补产后按倒排试排，仍无法满足 {due_s} 交付，建议交付不早于 {ef_s}。"
    )


def earliest_finish_finished(inp: ScheduleInput, finished_wo: Wo) -> date:
    """成品工单物理最快完工日（BR-47，不写回订单交期）。"""
    route = inp.routes.get(finished_wo.item_code)
    finished_item = inp.items[finished_wo.item_code]
    sph_fin = inp.sph_of(finished_wo.item_code, finished_wo.group_code)
    converts_fin = inp.converts_for(finished_wo.item_code)

    if route and route.needs_semi and route.semi_item_code:
        gross = gross_semi_board(finished_wo, route, finished_item)
        available = int(inp.stock.get(route.semi_item_code, Decimal(0)))
        net = max(0, gross - available)
        semi_item = inp.items[route.semi_item_code]
        sph_semi = inp.sph_of(semi_item.item_code, semi_item.group_code)
        converts_semi = inp.converts_for(semi_item.item_code)
        if net > 0:
            _, semi_end = count_workdays_forward(
                inp.calendar,
                semi_item.dept,
                semi_item.group_code,
                inp.today,
                net,
                sph_semi,
                sph_semi.crew_std,
                converts_semi,
                inp.config.reserved_ratio,
            )
            start = add_natural_days(semi_end, route.lead_time_days)
        else:
            start = max(inp.today, finished_wo.earliest_start)
        start = next_workday(
            inp.calendar, finished_wo.dept, finished_wo.group_code, start
        )
    else:
        start = max(inp.today, finished_wo.earliest_start)

    _, fin_end = count_workdays_forward(
        inp.calendar,
        finished_wo.dept,
        finished_wo.group_code,
        start,
        finished_wo.qty_board_plan,
        sph_fin,
        finished_wo.crew_plan,
        converts_fin,
        inp.config.reserved_ratio,
    )
    return fin_end


def detect_conflicts(inp: ScheduleInput, result: ScheduleResult) -> list[Conflict]:
    """全部软约束，只提示不阻断（BR-50）。"""
    conflicts: list[Conflict] = []
    wo_by_no = {wo.wo_no: wo for wo in result.wos}
    orders_by_no = {o.order_no: o for o in inp.orders}
    fence_end = inp.today + timedelta(days=inp.config.fence_days)

    for miss in result.unplaced:
        wo = wo_by_no.get(miss.wo_no)
        ef = None
        order = orders_by_no.get(wo.source_order_no) if wo else None
        if wo and wo.wo_type == WoType.FINISHED:
            ef = earliest_finish_finished(inp, wo)
            miss.earliest_finish = ef
        elif wo and wo.wo_type == WoType.SEMI:
            parent = wo_by_no.get(wo.parent_wo_no or "")
            if parent and parent.wo_type == WoType.FINISHED:
                ef = earliest_finish_finished(inp, parent)
        conflicts.append(
            Conflict(
                code=miss.code,
                level=ConflictLv.RED,
                wo_no=miss.wo_no,
                message=miss.reason,
                suggest=due_conflict_suggest(ef, order.due_date if order else None),
            )
        )

    for wo in result.wos:
        if wo.plan_start is not None and wo.plan_start < wo.earliest_start:
            order = orders_by_no.get(wo.source_order_no)
            if wo.wo_type == WoType.FINISHED:
                ef = earliest_finish_finished(inp, wo)
            elif wo.wo_type == WoType.SEMI:
                parent = wo_by_no.get(wo.parent_wo_no or "")
                ef = (
                    earliest_finish_finished(inp, parent)
                    if parent and parent.wo_type == WoType.FINISHED
                    else None
                )
            else:
                ef = None
            conflicts.append(
                Conflict(
                    code="E1",
                    level=ConflictLv.RED,
                    wo_no=wo.wo_no,
                    message="计划开工早于最早可排日",
                    suggest=due_conflict_suggest(ef, order.due_date if order else None)
                    if ef or order
                    else "DELAY_1D",
                )
            )

        if wo.wo_type == WoType.SEMI:
            placed = sum(t.qty_board for t in result.tasks if t.wo_no == wo.wo_no)
            semi_late = wo.plan_end is not None and wo.plan_end > wo.due_date
            semi_incomplete = placed < wo.qty_board_plan
            if semi_late or semi_incomplete:
                parent = wo_by_no.get(wo.parent_wo_no or "")
                finished = parent if parent and parent.wo_type == WoType.FINISHED else None
                ef = earliest_finish_finished(inp, finished) if finished else None
                order = orders_by_no.get(wo.source_order_no)
                due = order.due_date if order else wo.due_date
                gap = kit_semi_gap(result, wo)
                msg = (
                    e2_conflict_message(
                        wo.source_order_no,
                        due,
                        ef,
                        item_code=wo.item_code,
                        gross=gap[0] if gap else None,
                        from_stock=gap[1] if gap else None,
                        net=gap[2] if gap else wo.qty_board_plan,
                    )
                    if order
                    else "半成品来不及，无法满足成品开工"
                )
                conflicts.append(
                    Conflict(
                        code="E2",
                        level=ConflictLv.RED,
                        wo_no=wo.wo_no,
                        message=msg,
                        suggest=due_conflict_suggest(ef, due if order else None),
                    )
                )
            elif wo.plan_start is not None and wo.plan_start < fence_end:
                semi_task_id = next(
                    (t.task_id for t in result.tasks if t.wo_no == wo.wo_no),
                    None,
                )
                conflicts.append(
                    Conflict(
                        code="FROZEN",
                        level=ConflictLv.YELLOW,
                        wo_no=wo.wo_no,
                        task_id=semi_task_id,
                        dept=wo.dept.value,
                        group_code=wo.group_code.value,
                        cell_date=wo.plan_start,
                        message="半成品落在冻结区，需人工确认",
                        suggest="NOTIFY_SALES",
                    )
                )

        if wo.wo_type == WoType.FINISHED:
            order = orders_by_no.get(wo.source_order_no)
            if (
                order
                and order.ready_date
                and wo.plan_start is not None
                and wo.plan_start < order.ready_date
            ):
                conflicts.append(
                    Conflict(
                        code="E3",
                        level=ConflictLv.YELLOW,
                        wo_no=wo.wo_no,
                        message=f"包材预计 {order.ready_date.strftime('%m/%d')} 到，建议顺延",
                        suggest="DELAY_1D",
                    )
                )

        try:
            sph = inp.sph_of(wo.item_code, wo.group_code)
        except KeyError:
            sph = None
        if sph is not None:
            e8 = detect_e8(sph, wo.crew_plan)
            if e8 is not None:
                e8.wo_no = wo.wo_no
                conflicts.append(e8)

    hours_by_wc_day: dict[tuple[str, str, date], Decimal] = defaultdict(Decimal)
    for task in result.tasks:
        key = (task.dept.value, task.group_code.value, task.task_date)
        hours_by_wc_day[key] += task.hours_wall

    for (dept_val, group_val, task_date), total_wall in hours_by_wc_day.items():
        from engine.models import Dept, GroupCode

        dept = Dept(dept_val)
        group_code = GroupCode(group_val)
        limit = calendar_hours(
            inp.calendar,
            dept,
            group_code,
            task_date,
            attendance_scale=inp.config.attendance_scale_day_hours,
        )
        if total_wall > limit:
            over = total_wall - limit
            pct = (total_wall / limit * Decimal("100")).quantize(Decimal("0.1"))
            wc_label = f"{dept_val}:{group_val}"
            conflicts.append(
                Conflict(
                    code="E4",
                    level=ConflictLv.YELLOW,
                    task_id=None,
                    dept=dept_val,
                    group_code=group_val,
                    cell_date=task_date,
                    hours_wall_total=total_wall,
                    hours_wall_limit=limit,
                    message=(
                        f"{wc_label} {task_date} 墙钟工时超限："
                        f"合计 {total_wall:.2f}h / 日上限 {limit:.2f}h，"
                        f"超限 +{over:.2f}h（{pct}%）"
                    ),
                    suggest="ADD_CREW",
                )
            )

    for task in result.tasks:
        wo = wo_by_no.get(task.wo_no)
        if wo is None:
            continue
        try:
            sph = inp.sph_of(wo.item_code, wo.group_code)
        except KeyError:
            continue
        if sph.confidence.value == "LOW":
            conflicts.append(
                Conflict(
                    code="E5",
                    level=ConflictLv.GREY,
                    wo_no=wo.wo_no,
                    task_id=task.task_id,
                    message="SPH 未校准，结果仅供参考",
                    suggest=None,
                )
            )
            break

    return conflicts


def enrich_unplaced_earliest(inp: ScheduleInput, result: ScheduleResult) -> None:
    """E2 场景：为关联成品填充 unplaced.earliest_finish。"""
    finished_by_order = {
        wo.source_order_no: wo for wo in result.wos if wo.wo_type == WoType.FINISHED
    }
    for wo in result.wos:
        if wo.wo_type != WoType.SEMI:
            continue
        placed = sum(t.qty_board for t in result.tasks if t.wo_no == wo.wo_no)
        if placed >= wo.qty_board_plan and (wo.plan_end is None or wo.plan_end <= wo.due_date):
            continue
        fin = finished_by_order.get(wo.source_order_no)
        if fin is None:
            continue
        ef = earliest_finish_finished(inp, fin)
        result.unplaced.append(
            Unplaced(
                wo_no=fin.wo_no,
                code="E2",
                remaining=0,
                reason="半成品来不及",
                earliest_finish=ef,
            )
        )
        return
