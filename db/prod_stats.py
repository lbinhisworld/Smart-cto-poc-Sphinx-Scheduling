"""一部产能统计（只读聚合，不进 engine/）。"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.labor_cost_queries import WORK_CENTERS
from db.tables import (
    HrGroupAttendanceRow,
    InvInboundDailyRow,
    InvIssueRow,
    MdItemRow,
    MdUomConvertRow,
    ProdTimeReportRow,
    WoRow,
    WoTaskRow,
)
from engine.errors import UomConvertError
from engine.models import Uom, UomConvert
from engine.uom import convert_qty
from shared.labor_math import decimal_hours

DEPT1 = "FINISHED_DEPT"
GROUP_ORDER = ("MANUAL", "MOLD", "POURING")
CATEGORY_ORDER = {
    "MANUAL": ("手工模具", "棒子", "其他"),
    "MOLD": ("切片", "抹面", "糖花"),
    "POURING": ("logo",),
}
UOM_ZH = {
    "PCS": "枚",
    "BOARD": "版",
    "BOX": "盒",
    "PACK": "包",
    "BAG": "袋",
    "CARTON": "箱",
}
ISSUE_DESTS = ("INTERNAL", "RD", "SALES", "QC")
Q4 = Decimal("0.0001")


def _dec(value: object | None) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _q(value: Decimal) -> Decimal:
    return value.quantize(Q4, rounding=ROUND_HALF_UP)


def _f(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(_q(value))


def _i(value: Decimal | None) -> int | None:
    if value is None:
        return None
    return int(value.to_integral_value(rounding=ROUND_CEILING))


def _ceil_qty(qty: Decimal) -> Decimal:
    return qty.to_integral_value(rounding=ROUND_CEILING)


def _dates(date_from: date, date_to: date) -> list[date]:
    out: list[date] = []
    cur = date_from
    guard = 0
    while cur <= date_to and guard < 400:
        out.append(cur)
        cur += timedelta(days=1)
        guard += 1
    return out


def _group_label(group_code: str) -> str:
    return next((x[2] for x in WORK_CENTERS if x[0] == DEPT1 and x[1] == group_code), group_code)


def _item_map(session: Session) -> dict[str, MdItemRow]:
    return {r.item_code: r for r in session.scalars(select(MdItemRow)).all()}


def _converts_map(session: Session) -> dict[str, list[UomConvert]]:
    out: dict[str, list[UomConvert]] = {}
    for r in session.scalars(select(MdUomConvertRow)).all():
        out.setdefault(r.item_code, []).append(
            UomConvert(
                item_code=r.item_code,
                from_uom=Uom(r.from_uom),
                to_uom=Uom(r.to_uom),
                factor=Decimal(str(r.factor)),
            )
        )
    return out


def _to_display(qty_board: Decimal, item: MdItemRow, converts: list[UomConvert]) -> Decimal | None:
    display = getattr(item, "display_uom", None) or item.unit_sale or "BOARD"
    if display == "BOARD":
        return _ceil_qty(qty_board)
    try:
        return _ceil_qty(convert_qty(qty_board, Uom.BOARD, Uom(display), converts))
    except (UomConvertError, ValueError):
        return None


def _kg_for_task(task: WoTaskRow, item: MdItemRow | None) -> Decimal | None:
    snap = _dec(getattr(task, "kg_per_board_snap", None))
    if snap is not None:
        return snap
    if item is None:
        return None
    return _dec(getattr(item, "kg_per_board", None))


def _direct_hours(row: ProdTimeReportRow) -> Decimal | None:
    if row.status != "CONFIRMED":
        return None
    n = _dec(row.hours_normal)
    o = _dec(row.hours_ot)
    if n is not None or o is not None:
        return (n or Decimal("0")) + (o or Decimal("0"))
    if row.hours_man_actual is None:
        return None
    return decimal_hours(row.hours_man_actual)


def _indirect_hours(row: ProdTimeReportRow) -> Decimal:
    a = _dec(row.hours_indirect_normal) or Decimal("0")
    b = _dec(row.hours_indirect_ot) or Decimal("0")
    return a + b


def dept1_detail(session: Session, *, date_from: date, date_to: date) -> dict[str, Any]:
    days = _dates(date_from, date_to)
    items = _item_map(session)
    converts = _converts_map(session)
    tasks = session.scalars(
        select(WoTaskRow)
        .join(WoRow, WoTaskRow.wo_no == WoRow.wo_no)
        .where(WoTaskRow.dept == DEPT1)
        .where(WoTaskRow.task_date >= date_from)
        .where(WoTaskRow.task_date <= date_to)
        .where(WoRow.wo_type == "FINISHED")
    ).all()
    wos = {w.wo_no: w for w in session.scalars(select(WoRow).where(WoRow.wo_type == "FINISHED")).all()}

    buckets: dict[tuple[str, str, str, date], dict[str, Decimal | None | bool]] = {}
    seen_keys: set[tuple[str, str, str]] = set()

    for item in items.values():
        if item.dept != DEPT1 or item.is_semi:
            continue
        cat = getattr(item, "prod_category", "") or ""
        if not cat:
            continue
        uom = getattr(item, "display_uom", None) or item.unit_sale or "BOARD"
        seen_keys.add((item.group_code, cat, uom))

    for task in tasks:
        wo = wos.get(task.wo_no)
        item = items.get(wo.item_code) if wo else None
        if item is None:
            continue
        cat = getattr(item, "prod_category", "") or "其他"
        uom = getattr(item, "display_uom", None) or item.unit_sale or "BOARD"
        key = (task.group_code, cat, uom, task.task_date)
        seen_keys.add((task.group_code, cat, uom))
        cell = buckets.setdefault(
            key,
            {"qty_plan": Decimal("0"), "qty_actual": None, "box_kg": None, "missing_kg": False},
        )
        conv = converts.get(item.item_code, [])
        plan_disp = _to_display(Decimal(task.qty_board), item, conv)
        if plan_disp is not None:
            cell["qty_plan"] = (cell["qty_plan"] or Decimal("0")) + plan_disp
        if task.qty_actual is None:
            continue
        act_disp = _to_display(Decimal(task.qty_actual), item, conv)
        if act_disp is not None:
            prev = cell["qty_actual"]
            cell["qty_actual"] = (prev or Decimal("0")) + act_disp
        kg = _kg_for_task(task, item)
        if kg is None:
            cell["missing_kg"] = True
        else:
            add = Decimal(task.qty_actual) * kg
            cell["box_kg"] = (cell["box_kg"] or Decimal("0")) + add

    groups: list[dict[str, Any]] = []
    for group in GROUP_ORDER:
        cats_out: list[dict[str, Any]] = []
        for cat in CATEGORY_ORDER.get(group, ()):
            uoms = sorted({u for g, c, u in seen_keys if g == group and c == cat})
            units_out: list[dict[str, Any]] = []
            for uom in uoms:
                cells: dict[str, Any] = {}
                for day in days:
                    raw = buckets.get((group, cat, uom, day))
                    if raw is None:
                        cells[day.isoformat()] = {
                            "qty_plan": None,
                            "qty_actual": None,
                            "box_kg": None,
                            "missing_kg": False,
                        }
                    else:
                        cells[day.isoformat()] = {
                            "qty_plan": _i(raw["qty_plan"] if isinstance(raw["qty_plan"], Decimal) else None),
                            "qty_actual": _i(raw["qty_actual"] if isinstance(raw["qty_actual"], Decimal) else None),
                            "box_kg": _f(raw["box_kg"] if isinstance(raw["box_kg"], Decimal) else None),
                            "missing_kg": bool(raw["missing_kg"]),
                        }
                units_out.append(
                    {
                        "display_uom": uom,
                        "display_uom_label": UOM_ZH.get(uom, uom),
                        "cells": cells,
                    }
                )
            cats_out.append({"category": cat, "units": units_out})
        groups.append({"group_code": group, "group_label": _group_label(group), "categories": cats_out})

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "dates": [d.isoformat() for d in days],
        "groups": groups,
        "caliber": "未报工实际为空；盒当量=版×克重快照",
    }


def dept1_daily(session: Session, *, date_from: date, date_to: date) -> dict[str, Any]:
    days = _dates(date_from, date_to)
    items = _item_map(session)
    converts = _converts_map(session)
    tasks = session.scalars(
        select(WoTaskRow)
        .join(WoRow, WoTaskRow.wo_no == WoRow.wo_no)
        .where(WoTaskRow.dept == DEPT1)
        .where(WoTaskRow.task_date >= date_from)
        .where(WoTaskRow.task_date <= date_to)
        .where(WoRow.wo_type == "FINISHED")
    ).all()
    wos = {w.wo_no: w for w in session.scalars(select(WoRow).where(WoRow.wo_type == "FINISHED")).all()}
    reports = session.scalars(
        select(ProdTimeReportRow)
        .where(ProdTimeReportRow.schedule_dept == DEPT1)
        .where(ProdTimeReportRow.work_date >= date_from)
        .where(ProdTimeReportRow.work_date <= date_to)
    ).all()
    attendance = session.scalars(
        select(HrGroupAttendanceRow)
        .where(HrGroupAttendanceRow.schedule_dept == DEPT1)
        .where(HrGroupAttendanceRow.work_date >= date_from)
        .where(HrGroupAttendanceRow.work_date <= date_to)
    ).all()
    inbounds = session.scalars(
        select(InvInboundDailyRow)
        .where(InvInboundDailyRow.schedule_dept == DEPT1)
        .where(InvInboundDailyRow.work_date >= date_from)
        .where(InvInboundDailyRow.work_date <= date_to)
    ).all()
    issues = session.scalars(
        select(InvIssueRow)
        .where(InvIssueRow.schedule_dept == DEPT1)
        .where(InvIssueRow.work_date >= date_from)
        .where(InvIssueRow.work_date <= date_to)
    ).all()

    out_days: dict[str, dict[str, Any]] = {}
    period_box = Decimal("0")
    period_hours = Decimal("0")
    period_has = False

    for day in days:
        day_box: Decimal | None = None
        day_has_qty = False
        by_uom: dict[str, Decimal] = {}
        missing_kg = False
        for task in tasks:
            if task.task_date != day:
                continue
            wo = wos.get(task.wo_no)
            item = items.get(wo.item_code) if wo else None
            if item is None or task.qty_actual is None:
                continue
            day_has_qty = True
            uom = getattr(item, "display_uom", None) or item.unit_sale or "BOARD"
            disp = _to_display(Decimal(task.qty_actual), item, converts.get(item.item_code, []))
            if disp is not None:
                by_uom[uom] = by_uom.get(uom, Decimal("0")) + disp
            kg = _kg_for_task(task, item)
            if kg is None:
                missing_kg = True
                continue
            day_box = (day_box or Decimal("0")) + Decimal(task.qty_actual) * kg

        inbound_kg: Decimal | None = None
        for row in inbounds:
            if row.work_date != day:
                continue
            item = items.get(row.item_code)
            kg = _dec(row.kg_per_board_snap) or ( _dec(getattr(item, "kg_per_board", None)) if item else None)
            if kg is None:
                continue
            inbound_kg = (inbound_kg or Decimal("0")) + Decimal(row.qty_board) * kg

        issue_kg = {d: Decimal("0") for d in ISSUE_DESTS}
        for row in issues:
            if row.work_date != day:
                continue
            item = items.get(row.item_code)
            kg = _dec(row.kg_per_board_snap) or (_dec(getattr(item, "kg_per_board", None)) if item else None)
            if kg is None:
                continue
            dest = row.dest if row.dest in issue_kg else "INTERNAL"
            issue_kg[dest] += Decimal(row.qty_board) * kg

        hours_direct: Decimal | None = None
        hours_indirect = Decimal("0")
        headcount = 0
        for row in reports:
            if row.work_date != day:
                continue
            dh = _direct_hours(row)
            if dh is not None:
                hours_direct = (hours_direct or Decimal("0")) + dh
            hours_indirect += _indirect_hours(row)
        for row in attendance:
            if row.work_date == day:
                headcount += int(row.headcount_present or 0)

        box_per_hour = None
        if day_has_qty and day_box is not None and hours_direct is not None and hours_direct > 0:
            box_per_hour = day_box / hours_direct
            period_box += day_box
            period_hours += hours_direct
            period_has = True

        variance = None
        if day_box is not None and inbound_kg is not None:
            variance = day_box - inbound_kg

        hours_normal = Decimal("0")
        hours_ot = Decimal("0")
        for row in reports:
            if row.work_date != day or row.status != "CONFIRMED":
                continue
            if row.hours_normal is not None or row.hours_ot is not None:
                hours_normal += _dec(row.hours_normal) or Decimal("0")
                hours_ot += _dec(row.hours_ot) or Decimal("0")
            elif row.hours_man_actual is not None:
                hours_normal += decimal_hours(row.hours_man_actual)

        out_days[day.isoformat()] = {
            "box_kg": _f(day_box) if day_has_qty else None,
            "inbound_box_kg": _f(inbound_kg),
            "variance_box_kg": _f(variance),
            "issues": {k: _f(v) or 0.0 for k, v in issue_kg.items()},
            "headcount": headcount or None,
            "hours_normal": _f(hours_normal) if hours_direct is not None else None,
            "hours_ot": _f(hours_ot) if hours_direct is not None else None,
            "hours_direct": _f(hours_direct),
            "hours_indirect": _f(hours_indirect) if hours_direct is not None else None,
            "hours_total": _f((hours_direct or Decimal("0")) + hours_indirect) if hours_direct is not None else None,
            "by_uom": {k: _i(v) for k, v in by_uom.items()},
            "box_per_hour": _f(box_per_hour),
            "missing_kg": missing_kg,
        }

    period_bph = (period_box / period_hours) if period_has and period_hours > 0 else None
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "dates": [d.isoformat() for d in days],
        "days": out_days,
        "period": {
            "box_kg": _f(period_box) if period_has else None,
            "hours_direct": _f(period_hours) if period_has else None,
            "box_per_hour": _f(period_bph),
        },
        "caliber": "盒/H=已报工日盒当量÷直接工时（不含间接）；未报工日不进区间",
    }


def dept1_efficiency(session: Session, *, date_from: date, date_to: date) -> dict[str, Any]:
    daily = dept1_daily(session, date_from=date_from, date_to=date_to)
    groups: dict[str, dict[str, Decimal]] = {g: {"box": Decimal("0"), "hours": Decimal("0")} for g in GROUP_ORDER}
    items = _item_map(session)
    tasks = session.scalars(
        select(WoTaskRow)
        .join(WoRow, WoTaskRow.wo_no == WoRow.wo_no)
        .where(WoTaskRow.dept == DEPT1)
        .where(WoTaskRow.task_date >= date_from)
        .where(WoTaskRow.task_date <= date_to)
        .where(WoRow.wo_type == "FINISHED")
    ).all()
    wos = {w.wo_no: w for w in session.scalars(select(WoRow).where(WoRow.wo_type == "FINISHED")).all()}
    reports = session.scalars(
        select(ProdTimeReportRow)
        .where(ProdTimeReportRow.schedule_dept == DEPT1)
        .where(ProdTimeReportRow.work_date >= date_from)
        .where(ProdTimeReportRow.work_date <= date_to)
        .where(ProdTimeReportRow.status == "CONFIRMED")
    ).all()
    hours_by_gd: dict[tuple[str, date], Decimal] = {}
    for row in reports:
        dh = _direct_hours(row)
        if dh is None:
            continue
        hours_by_gd[(row.group_code, row.work_date)] = hours_by_gd.get((row.group_code, row.work_date), Decimal("0")) + dh

    qty_days: dict[tuple[str, date], Decimal] = {}
    for task in tasks:
        if task.qty_actual is None:
            continue
        wo = wos.get(task.wo_no)
        item = items.get(wo.item_code) if wo else None
        kg = _kg_for_task(task, item)
        if kg is None:
            continue
        key = (task.group_code, task.task_date)
        qty_days[key] = qty_days.get(key, Decimal("0")) + Decimal(task.qty_actual) * kg

    for (group, day), box in qty_days.items():
        hours = hours_by_gd.get((group, day))
        if hours is None or hours <= 0:
            continue
        groups[group]["box"] += box
        groups[group]["hours"] += hours

    group_rows = []
    for group in GROUP_ORDER:
        box = groups[group]["box"]
        hours = groups[group]["hours"]
        group_rows.append(
            {
                "group_code": group,
                "group_label": _group_label(group),
                "box_kg": _f(box) if hours > 0 else None,
                "hours_direct": _f(hours) if hours > 0 else None,
                "box_per_hour": _f(box / hours) if hours > 0 else None,
            }
        )
    return {
        "date_from": daily["date_from"],
        "date_to": daily["date_to"],
        "dates": daily["dates"],
        "days": daily["days"],
        "period": daily["period"],
        "groups": group_rows,
        "caliber": daily["caliber"],
    }
