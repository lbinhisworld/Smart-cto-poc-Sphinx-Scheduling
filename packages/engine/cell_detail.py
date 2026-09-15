"""组×日单元格与单任务指标（纯函数）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.capacity import calendar_day, calendar_hours
from engine.models import Dept, GroupCode, Order, ScheduleInput, ScheduleResult, WoTask

HOURS_Q = Decimal("0.0001")


def _q4(value: Decimal) -> Decimal:
    return value.quantize(HOURS_Q)


def _sum_wall(tasks: list[WoTask]) -> Decimal:
    return _q4(sum((t.hours_wall for t in tasks), Decimal(0)))


def _sum_man(tasks: list[WoTask]) -> Decimal:
    return _q4(sum((t.hours_man for t in tasks), Decimal(0)))


def compute_metrics(
    tasks: list[WoTask],
    *,
    available_wall: Decimal,
    headcount: int,
    reserved_ratio: Decimal,
) -> dict:
    wall = _sum_wall(tasks)
    man = _sum_man(tasks)
    effective_wall = _q4(available_wall * (Decimal(1) - reserved_ratio))
    if effective_wall <= 0:
        cap_util = Decimal(0)
    else:
        cap_util = _q4(wall / effective_wall)
    denom_man = _q4(available_wall * Decimal(headcount)) if headcount else Decimal(0)
    if denom_man <= 0:
        lab_util = Decimal(0)
    else:
        lab_util = _q4(man / denom_man)

    return {
        "wall_clock_hours": wall,
        "hours_man": man,
        "available_wall_hours": available_wall,
        "effective_wall_hours": effective_wall,
        "available_man_hours": denom_man,
        "capacity_utilization": cap_util,
        "labor_utilization": lab_util,
        "capacity_formula": (
            f"产能利用率 = 墙钟合计 {wall} h ÷ 有效可用 {effective_wall} h "
            f"(= {available_wall} h × (1 − {reserved_ratio}))"
        ),
        "labor_formula": (
            f"人·时利用率 = 人·时合计 {man} h ÷ 可用人工 {denom_man} h "
            f"(= {headcount} 人 × {available_wall} h)"
        ),
        "wall_formula": "墙钟工时 = 本范围内各任务 hours_wall 之和（单任务见 qty÷组产能）",
    }


def build_cell_detail(
    inp: ScheduleInput,
    result: ScheduleResult,
    *,
    dept: Dept,
    group_code: GroupCode,
    task_date: date,
    orders_by_no: dict[str, Order],
    focus_task_id: int | None,
) -> dict:
    wo_map = {w.wo_no: w for w in result.wos}
    cell_tasks = [
        t
        for t in result.tasks
        if t.dept == dept and t.group_code == group_code and t.task_date == task_date
    ]
    cal_row = calendar_day(inp.calendar, dept, group_code, task_date)
    available_wall = calendar_hours(inp.calendar, dept, group_code, task_date)
    headcount = cal_row.headcount if cal_row else 0
    reserved = inp.config.reserved_ratio

    cell_metrics = compute_metrics(
        cell_tasks,
        available_wall=available_wall,
        headcount=headcount,
        reserved_ratio=reserved,
    )

    scope_tasks = cell_tasks
    task_metrics = None
    if focus_task_id is not None:
        scope_tasks = [t for t in cell_tasks if t.task_id == focus_task_id]
        if scope_tasks:
            task_metrics = compute_metrics(
                scope_tasks,
                available_wall=available_wall,
                headcount=headcount,
                reserved_ratio=reserved,
            )

    order_rows: dict[str, dict] = {}
    for t in cell_tasks:
        wo = wo_map.get(t.wo_no)
        if wo is None:
            continue
        o = orders_by_no.get(wo.source_order_no)
        key = wo.source_order_no
        if key not in order_rows:
            order_rows[key] = {
                "order_no": key,
                "customer": o.customer if o else "",
                "sales_name": o.sales_name if o else "",
                "item_code": wo.item_code,
                "wo_nos": [],
                "qty_board_in_cell": 0,
            }
        order_rows[key]["wo_nos"].append(wo.wo_no)
        order_rows[key]["qty_board_in_cell"] += t.qty_board

    tasks_payload = []
    for t in cell_tasks:
        wo = wo_map.get(t.wo_no)
        tasks_payload.append(
            {
                "task_id": t.task_id,
                "wo_no": t.wo_no,
                "source_order_no": wo.source_order_no if wo else "",
                "item_code": wo.item_code if wo else "",
                "qty_board": t.qty_board,
                "hours_wall": str(t.hours_wall),
                "hours_man": str(t.hours_man),
                "crew_plan": t.crew_plan,
            }
        )

    return {
        "dept": dept.value,
        "group_code": group_code.value,
        "task_date": task_date.isoformat(),
        "focus_task_id": focus_task_id,
        "is_workday": bool(cal_row and cal_row.is_workday),
        "headcount": headcount,
        "reserved_ratio": str(reserved),
        "tasks": tasks_payload,
        "orders": sorted(order_rows.values(), key=lambda r: r["order_no"]),
        "cell_metrics": {k: str(v) if isinstance(v, Decimal) else v for k, v in cell_metrics.items()},
        "task_metrics": (
            {k: str(v) if isinstance(v, Decimal) else v for k, v in task_metrics.items()}
            if task_metrics
            else None
        ),
    }
