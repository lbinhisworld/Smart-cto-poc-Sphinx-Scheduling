"""仓储：排产路径禁止写 so_order.due_date（BR-27）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.plan_store import current_plan_version, load_schedule_result, save_schedule_result
from db.snapshot import load_schedule_input
from db.tables import SoOrderRow
from engine.models import ScheduleResult
from engine.schedule import schedule


class DueDateWriteForbiddenError(RuntimeError):
    """排产仓储层不得改写订单交期。"""


def get_order_due_date(session: Session, order_no: str) -> date:
    row = session.scalar(select(SoOrderRow).where(SoOrderRow.order_no == order_no))
    if row is None:
        raise KeyError(order_no)
    return row.due_date


def update_order_due_date_by_user(session: Session, order_no: str, due_date: date) -> None:
    """仅订单 PATCH（人工改交期）可调用。"""
    row = session.scalar(select(SoOrderRow).where(SoOrderRow.order_no == order_no))
    if row is None:
        raise KeyError(order_no)
    row.due_date = due_date


def run_schedule(
    session: Session,
    *,
    today: date,
    order_nos: list[str],
    reserved_ratio: Decimal = Decimal("0"),
    persist: bool,
    trigger: str = "初始排产",
) -> tuple[ScheduleResult, int]:
    """执行倒排。persist=False 为 what-if。"""
    inp = load_schedule_input(
        session,
        today=today,
        order_nos=order_nos,
        reserved_ratio=reserved_ratio,
    )
    result = schedule(inp)
    version = current_plan_version(session)
    if persist:
        version = save_schedule_result(session, result, trigger=trigger)
    return result, version
