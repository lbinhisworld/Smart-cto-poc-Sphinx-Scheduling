"""DB + yaml → ScheduleInput（today 仅来自请求）。"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.attendance_capacity import apply_attendance_to_calendar
from db.config_loader import load_schedule_config
from db.tables import (
    MdBomLineRow,
    MdCapacityCalendarRow,
    MdItemRouteRow,
    MdItemRow,
    MdSphRow,
    MdUomConvertRow,
    SoOrderRow,
    StockRow,
    WoRow,
    WoTaskRow,
)
from engine.models import (
    BomLine,
    CalendarDay,
    ComponentRole,
    Confidence,
    Dept,
    GroupCode,
    Item,
    ItemRoute,
    Order,
    ScheduleConfig,
    ScheduleInput,
    Sph,
    SphBasis,
    Uom,
    UomConvert,
    WoStatus,
    WoTask,
)


def _dec(value) -> Decimal:
    return Decimal(str(value))


def load_schedule_input(
    session: Session,
    *,
    today: date,
    order_nos: list[str] | None = None,
    config_override: ScheduleConfig | None = None,
    reserved_ratio: Decimal | None = Decimal("0"),
) -> ScheduleInput:
    cfg = config_override or load_schedule_config(
        reserved_ratio=reserved_ratio if reserved_ratio is not None else None
    )

    items = {
        r.item_code: Item(
            item_code=r.item_code,
            item_name=r.item_name,
            dept=Dept(r.dept),
            group_code=GroupCode(r.group_code),
            unit_sale=Uom(r.unit_sale),
            pcs_per_board=r.pcs_per_board,
            board_per_box=_dec(r.board_per_box),
            loss_rate=_dec(r.loss_rate),
            color=r.color,
            is_semi=r.is_semi,
            computable=r.computable,
        )
        for r in session.scalars(select(MdItemRow)).all()
    }
    uom: dict[str, list[UomConvert]] = {}
    for r in session.scalars(select(MdUomConvertRow)).all():
        uom.setdefault(r.item_code, []).append(
            UomConvert(
                item_code=r.item_code,
                from_uom=Uom(r.from_uom),
                to_uom=Uom(r.to_uom),
                factor=_dec(r.factor),
            )
        )
    routes = {
        r.item_code: ItemRoute(
            item_code=r.item_code,
            needs_semi=r.needs_semi,
            semi_item_code=r.semi_item_code,
            semi_board_per_box=_dec(r.semi_board_per_box) if r.semi_board_per_box else None,
            lead_time_days=r.lead_time_days,
            changeover_min=r.changeover_min,
        )
        for r in session.scalars(select(MdItemRouteRow)).all()
    }
    sph = {
        (r.item_code, r.group_code): Sph(
            item_code=r.item_code,
            group_code=GroupCode(r.group_code),
            sph_value=_dec(r.sph_value),
            sph_basis=SphBasis(r.sph_basis),
            sph_crew=r.sph_crew,
            sph_uom=Uom(r.sph_uom),
            crew_std=r.crew_std,
            confidence=Confidence(r.confidence),
            effective_date=r.effective_date,
            source=r.source,
        )
        for r in session.scalars(select(MdSphRow)).all()
    }
    calendar = [
        CalendarDay(
            dept=Dept(getattr(row, "dept", None) or "FINISHED_DEPT"),
            group_code=GroupCode(row.group_code),
            work_date=row.work_date,
            is_workday=row.is_workday,
            hours_per_day=_dec(row.hours_per_day),
            headcount=row.headcount,
            reserved_ratio=_dec(row.reserved_ratio),
        )
        for row in session.scalars(select(MdCapacityCalendarRow)).all()
    ]
    calendar = apply_attendance_to_calendar(session, calendar)
    stock = {r.item_code: _dec(r.qty_available) for r in session.scalars(select(StockRow)).all()}

    bom_lines: dict[str, list[BomLine]] = {}
    for row in session.scalars(select(MdBomLineRow)).all():
        bl = BomLine(
            parent_item_code=row.parent_item_code,
            line_no=row.line_no,
            component_item_code=row.component_item_code,
            component_role=ComponentRole(row.component_role),
            qty_per_parent=_dec(row.qty_per_parent),
            qty_basis_uom=Uom(row.qty_basis_uom),
            scrap_rate=_dec(row.scrap_rate) if row.scrap_rate is not None else None,
            offset_days=row.offset_days,
            lead_time_days=row.lead_time_days,
            kit_critical=row.kit_critical,
        )
        bom_lines.setdefault(bl.parent_item_code, []).append(bl)

    q = select(SoOrderRow)
    if order_nos:
        q = q.where(SoOrderRow.order_no.in_(order_nos))
    orders = [
        Order(
            order_no=r.order_no,
            customer=r.customer,
            sales_name=r.sales_name or "",
            item_code=r.item_code,
            qty_order=_dec(r.qty_order),
            unit=Uom(r.unit),
            due_date=r.due_date,
            ready_date=r.ready_date,
            customer_level=r.customer_level,
            amount=_dec(r.amount),
            is_urgent=r.is_urgent,
            schedule_phase=r.schedule_phase or "PENDING",
        )
        for r in session.scalars(q).all()
    ]

    locked_tasks = _locked_tasks_for_fence(session, today, cfg.fence_days)
    return ScheduleInput(
        today=today,
        orders=orders,
        items=items,
        uom=uom,
        routes=routes,
        bom_lines=bom_lines,
        sph=sph,
        calendar=calendar,
        stock=stock,
        locked_tasks=locked_tasks,
        config=cfg,
    )


def _locked_tasks_for_fence(session: Session, today: date, fence_days: int) -> list[WoTask]:
    """BR-40/41：冻结区内已 RELEASED 任务占位。"""
    fence_end = today + timedelta(days=fence_days)
    rows = session.scalars(
        select(WoTaskRow)
        .join(WoRow, WoTaskRow.wo_no == WoRow.wo_no)
        .where(WoRow.status == WoStatus.RELEASED.value)
        .where(WoRow.plan_start.is_not(None))
        .where(WoRow.plan_start < fence_end)
    ).all()
    return [
        WoTask(
            task_id=r.task_id,
            wo_no=r.wo_no,
            dept=Dept(getattr(r, "dept", None) or "FINISHED_DEPT"),
            group_code=GroupCode(r.group_code),
            task_date=r.task_date,
            qty_board=r.qty_board,
            hours_wall=_dec(r.hours_wall),
            hours_man=_dec(r.hours_man),
            crew_plan=r.crew_plan,
            seq=r.seq,
            changeover_min=r.changeover_min,
            plan_version=r.plan_version,
        )
        for r in rows
    ]
