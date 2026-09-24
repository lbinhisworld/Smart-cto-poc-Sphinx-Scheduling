"""仓储：排产路径禁止写 so_order.due_date（BR-27）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.plan_store import (
    current_plan_version,
    load_schedule_result,
    log_insert,
    save_schedule_result,
)
from db.prod_stats_seed import is_capacity_fixture_order
from db.snapshot import load_schedule_input
from db.tables import SoOrderRow
from engine.insert import schedule_insert
from engine.models import InsertStrategy, Order, ScheduleResult, Uom
from engine.schedule import schedule


def get_order_due_date(session: Session, order_no: str) -> date:
    row = session.scalar(select(SoOrderRow).where(SoOrderRow.order_no == order_no))
    if row is None:
        raise KeyError(order_no)
    return row.due_date


def list_order_nos(session: Session) -> list[str]:
    return list(session.scalars(select(SoOrderRow.order_no)).all())


def list_orders(session: Session) -> list[Order]:
    rows = session.scalars(select(SoOrderRow).order_by(SoOrderRow.order_no)).all()
    return [
        Order(
            order_no=r.order_no,
            customer=r.customer,
            sales_name=r.sales_name or "",
            item_code=r.item_code,
            qty_order=Decimal(str(r.qty_order)),
            unit=Uom(r.unit),
            due_date=r.due_date,
            ready_date=r.ready_date,
            customer_level=r.customer_level,
            amount=Decimal(str(r.amount)),
            is_urgent=r.is_urgent,
            schedule_phase=r.schedule_phase or "PENDING",
        )
        for r in rows
        if not is_capacity_fixture_order(r.order_no, r.order_source)
    ]


def get_order(session: Session, order_no: str) -> Order:
    row = session.scalar(select(SoOrderRow).where(SoOrderRow.order_no == order_no))
    if row is None:
        raise KeyError(order_no)
    return Order(
        order_no=row.order_no,
        customer=row.customer,
        sales_name=row.sales_name or "",
        item_code=row.item_code,
        qty_order=Decimal(str(row.qty_order)),
        unit=Uom(row.unit),
        due_date=row.due_date,
        ready_date=row.ready_date,
        customer_level=row.customer_level,
        amount=Decimal(str(row.amount)),
        is_urgent=row.is_urgent,
        schedule_phase=row.schedule_phase or "PENDING",
    )


def create_order(session: Session, order: Order) -> None:
    session.add(
        SoOrderRow(
            order_no=order.order_no,
            customer=order.customer,
            sales_name=order.sales_name or "",
            item_code=order.item_code,
            qty_order=str(order.qty_order),
            unit=order.unit.value if hasattr(order.unit, "value") else order.unit,
            due_date=order.due_date,
            ready_date=order.ready_date,
            customer_level=order.customer_level,
            amount=str(order.amount),
            is_urgent=order.is_urgent,
            schedule_phase=order.schedule_phase or "PENDING",
        )
    )


def set_group_headcount(session: Session, dept: str, group_code: str, headcount: int) -> int:
    """只改这一组日历上的在编。不改订单交期，不触发倒排。"""
    from db.tables import MdCapacityCalendarRow

    rows = list(
        session.scalars(
            select(MdCapacityCalendarRow).where(
                MdCapacityCalendarRow.dept == dept,
                MdCapacityCalendarRow.group_code == group_code,
            )
        ).all()
    )
    for row in rows:
        row.headcount = headcount
    return len(rows)


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
) -> tuple[ScheduleResult, int, str]:
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
    from db.schedule_run_log import write_schedule_run_log

    run_id = write_schedule_run_log(
        inp,
        result,
        trigger=trigger,
        plan_version=version,
        persist=persist,
    )
    return result, version, run_id


def run_insert_trial(
    session: Session,
    *,
    urgent_order_no: str,
    today: date,
    reserved_ratio: Decimal = Decimal("0"),
):
    """插单四策略试排（不落库）。"""
    order = get_order(session, urgent_order_no)
    order_nos = list_order_nos(session)
    inp = load_schedule_input(
        session,
        today=today,
        order_nos=order_nos,
        reserved_ratio=reserved_ratio,
    )
    baseline_ver = current_plan_version(session)
    if baseline_ver > 0:
        baseline = load_schedule_result(session, baseline_ver)
    else:
        others = [no for no in order_nos if no != urgent_order_no]
        baseline = schedule(
            load_schedule_input(
                session, today=today, order_nos=others, reserved_ratio=reserved_ratio
            )
        )
    return schedule_insert(inp, order, baseline=baseline)


def apply_insert_strategy(
    session: Session,
    *,
    urgent_order_no: str,
    today: date,
    strategy: InsertStrategy,
    reason: str,
    requester: str = "api",
    reserved_ratio: Decimal = Decimal("0"),
) -> tuple[ScheduleResult, int]:
    compare = run_insert_trial(
        session,
        urgent_order_no=urgent_order_no,
        today=today,
        reserved_ratio=reserved_ratio,
    )
    picked = next(s for s in compare.strategies if s.strategy == strategy)
    before = current_plan_version(session)
    after = save_schedule_result(session, picked.result, trigger=f"插单-{strategy.value}")
    from db.schedule_run_log import write_schedule_run_log

    write_schedule_run_log(
        load_schedule_input(
            session,
            today=today,
            order_nos=list_order_nos(session),
            reserved_ratio=reserved_ratio,
        ),
        picked.result,
        trigger=f"插单-{strategy.value}",
        plan_version=after,
        persist=True,
    )
    wo_no = next(
        (w.wo_no for w in picked.result.wos if w.source_order_no == urgent_order_no),
        urgent_order_no,
    )
    log_insert(
        session,
        wo_no=wo_no,
        requester=requester,
        reason=reason,
        strategy=strategy.value,
        version_before=before,
        version_after=after,
    )
    from db.order_lifecycle import add_to_scheduling_pool

    add_to_scheduling_pool(session, [urgent_order_no])
    return picked.result, after
