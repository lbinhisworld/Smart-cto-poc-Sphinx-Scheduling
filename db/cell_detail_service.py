"""组×日 / 任务详情（DB + 引擎）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from db.plan_store import current_plan_version, load_schedule_result
from db.snapshot import load_schedule_input
from engine.cell_detail import build_cell_detail
from engine.models import Dept, GroupCode, ScheduleResult, WoTask


def resolve_cell_detail(
    session: Session,
    *,
    today: date,
    dept: str,
    group_code: str,
    task_date: date,
    focus_task_id: int | None = None,
    plan_version: int | None = None,
    result_override: ScheduleResult | None = None,
    tasks_override: list[WoTask] | None = None,
    reserved_ratio: Decimal | None = Decimal("0"),
) -> dict:
    if result_override is not None:
        result = result_override
    else:
        ver = plan_version or current_plan_version(session)
        if ver <= 0:
            raise ValueError("尚无计划版本")
        result = load_schedule_result(session, ver)

    if tasks_override is not None:
        result = result.model_copy(update={"tasks": tasks_override})

    order_nos = sorted({wo.source_order_no for wo in result.wos})
    inp = load_schedule_input(
        session,
        today=today,
        order_nos=order_nos,
        reserved_ratio=reserved_ratio,
    )
    orders_by_no = {o.order_no: o for o in inp.orders}
    return build_cell_detail(
        inp,
        result,
        dept=Dept(dept),
        group_code=GroupCode(group_code),
        task_date=task_date,
        orders_by_no=orders_by_no,
        focus_task_id=focus_task_id,
    )
