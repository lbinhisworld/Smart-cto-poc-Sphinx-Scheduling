"""一部产能统计拟真数据（与排程 plan_version 隔离，不进倒排看板）。"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.tables import (
    AppSettingRow,
    HrGroupAttendanceRow,
    InvInboundDailyRow,
    InvIssueRow,
    MdItemRow,
    ProdTimeReportRow,
    SoOrderRow,
    WoRow,
    WoTaskRow,
)

STATS_VERSION_KEY = "dept1_stats_demo_version"
STATS_VERSION = "2026-09-17-dept1-v2"
DEMO_PLAN_VERSION = 9001
WO_PREFIX = "WO-D1S-"
SO_PREFIX = "SO-D1S-"
SOURCE = "DEMO_D1"
DEPT = "FINISHED_DEPT"
ANCHOR_TODAY = date(2026, 9, 15)

def _weekdays(start: date, end: date) -> tuple[date, ...]:
    out: list[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return tuple(out)


# 9/1–9/25 工作日报满（图好看）；月末 28–30 只留计划，演示未报工格空
REPORTED_DAYS = _weekdays(date(2026, 9, 1), date(2026, 9, 25))
PLAN_ONLY_DAYS = _weekdays(date(2026, 9, 28), date(2026, 9, 30))
WEEK_QTY = (0.90, 1.00, 1.10, 1.06, 0.92)
WEEK_HRS = (1.06, 1.00, 0.93, 0.98, 1.12)


def _qty_factor(idx: int, n: int, weekday: int) -> float:
    trend = 0.86 + 0.28 * math.sin(math.pi * idx / max(n - 1, 1))
    return trend * WEEK_QTY[weekday]


def _hours_factor(idx: int, n: int, weekday: int) -> float:
    wave = 1.0 + 0.16 * math.sin(math.pi * idx / max(n - 1, 1) + 1.35)
    return wave * WEEK_HRS[weekday]


def _actual_ratio(idx: int) -> float:
    return 0.91 + 0.10 * (0.5 + 0.5 * math.sin(idx * 0.73 + 0.35))


def _inbound_ratio(idx: int) -> float:
    return 0.90 + 0.08 * (0.5 + 0.5 * math.sin(idx * 0.51 + 1.1))

# item, group, 基准版数（再乘日系数）
LINES = (
    ("P1", "MANUAL", 6200),
    ("P1M", "MANUAL", 2200),
    ("P1L", "MANUAL", 900),
    ("P2", "MOLD", 5400),
    ("P5", "MOLD", 4000),
    ("P9", "MOLD", 1600),
    ("P4", "POURING", 4300),
    ("P7", "POURING", 2800),
    ("P8", "POURING", 1600),
)

# 正常 / 加班 / 间接 人·时；出勤人数
HOURS = {
    "MANUAL": (228, 42, 14, 29),
    "MOLD": (312, 58, 18, 38),
    "POURING": (196, 36, 10, 26),
}


def _set_version(session: Session, version: str) -> None:
    row = session.get(AppSettingRow, STATS_VERSION_KEY)
    if row is None:
        session.add(AppSettingRow(key=STATS_VERSION_KEY, value=version))
    else:
        row.value = version


def _stored_version(session: Session) -> str | None:
    row = session.get(AppSettingRow, STATS_VERSION_KEY)
    return row.value if row else None


def _clear_demo(session: Session) -> None:
    wo_nos = list(
        session.scalars(select(WoRow.wo_no).where(WoRow.wo_no.startswith(WO_PREFIX))).all()
    )
    if wo_nos:
        session.execute(delete(WoTaskRow).where(WoTaskRow.wo_no.in_(wo_nos)))
        session.execute(delete(WoRow).where(WoRow.wo_no.in_(wo_nos)))
    session.execute(delete(SoOrderRow).where(SoOrderRow.order_no.startswith(SO_PREFIX)))
    session.execute(
        delete(ProdTimeReportRow).where(ProdTimeReportRow.plan_version == DEMO_PLAN_VERSION)
    )
    session.execute(delete(InvInboundDailyRow).where(InvInboundDailyRow.source == SOURCE))
    session.execute(delete(InvIssueRow).where(InvIssueRow.created_by == SOURCE))
    session.execute(delete(HrGroupAttendanceRow).where(HrGroupAttendanceRow.source == SOURCE))
    session.flush()


def _scale(base: int, factor: float) -> int:
    return max(1, int(round(base * factor)))


def _plant(session: Session) -> dict:
    items = {r.item_code: r for r in session.scalars(select(MdItemRow)).all()}
    planted_lines = 0
    n_rep = len(REPORTED_DAYS)
    for idx, work_date in enumerate(REPORTED_DAYS):
        wd = work_date.weekday()
        df = _qty_factor(idx, n_rep, wd)
        ar = _actual_ratio(idx)
        ir = _inbound_ratio(idx)
        hf = _hours_factor(idx, n_rep, wd)
        for item_code, group_code, base in LINES:
            item = items.get(item_code)
            if item is None:
                continue
            plan = _scale(base, df)
            actual = _scale(plan, ar)
            kg = item.kg_per_board
            wo_no = f"{WO_PREFIX}{item_code}-{work_date.strftime('%m%d')}"
            so_no = f"{SO_PREFIX}{item_code}-{work_date.strftime('%m%d')}"
            session.add(
                SoOrderRow(
                    order_no=so_no,
                    customer="一部日报拟真（不进排程池）",
                    sales_name="演示",
                    item_code=item_code,
                    qty_order=str(plan),
                    unit="BOARD",
                    due_date=work_date + timedelta(days=2),
                    customer_level=3,
                    amount="0",
                    is_urgent=False,
                    schedule_phase="DONE",
                    order_source=SOURCE,
                )
            )
            session.add(
                WoRow(
                    wo_no=wo_no,
                    wo_type="FINISHED",
                    source_order_no=so_no,
                    item_code=item_code,
                    group_code=group_code,
                    dept=DEPT,
                    qty_order=str(plan),
                    qty_board_plan=plan,
                    due_date=work_date + timedelta(days=2),
                    plan_start=work_date,
                    plan_end=work_date,
                    earliest_start=work_date,
                    crew_plan=8,
                    status="DONE",
                    plan_version=DEMO_PLAN_VERSION,
                    qty_board_done=actual,
                )
            )
            session.add(
                WoTaskRow(
                    wo_no=wo_no,
                    dept=DEPT,
                    group_code=group_code,
                    task_date=work_date,
                    qty_board=plan,
                    hours_wall="8",
                    hours_man="24",
                    crew_plan=8,
                    seq=1,
                    plan_version=DEMO_PLAN_VERSION,
                    qty_actual=actual,
                    kg_per_board_snap=str(kg) if kg is not None else None,
                )
            )
            inbound = _scale(actual, ir)
            session.add(
                InvInboundDailyRow(
                    work_date=work_date,
                    schedule_dept=DEPT,
                    group_code=group_code,
                    item_code=item_code,
                    qty_board=inbound,
                    kg_per_board_snap=str(kg) if kg is not None else None,
                    source=SOURCE,
                    note="拟真入库",
                    created_at=datetime(2026, 9, 15, 8, 0, 0),
                    created_by=SOURCE,
                )
            )
            planted_lines += 1
        for group_code, (normal, ot, indirect, head) in HOURS.items():
            session.add(
                ProdTimeReportRow(
                    work_date=work_date,
                    schedule_dept=DEPT,
                    group_code=group_code,
                    plan_version=DEMO_PLAN_VERSION,
                    hours_man_planned=str(_q(Decimal(normal + ot) * Decimal(str(hf)))),
                    hours_man_actual=str(_q(Decimal(normal + ot) * Decimal(str(hf)))),
                    headcount_actual=head,
                    status="CONFIRMED",
                    reported_by="拟真",
                    confirmed_at=datetime(2026, 9, 15, 18, 0, 0),
                    note="一部日报拟真",
                    hours_normal=str(_q(Decimal(normal) * Decimal(str(hf)))),
                    hours_ot=str(_q(Decimal(ot) * Decimal(str(hf)))),
                    headcount_indirect=3 if group_code == "MOLD" else 2,
                    hours_indirect_normal=str(_q(Decimal(indirect) * Decimal(str(hf)))),
                    hours_indirect_ot="0",
                )
            )
            session.add(
                HrGroupAttendanceRow(
                    schedule_dept=DEPT,
                    group_code=group_code,
                    work_date=work_date,
                    headcount_present=head,
                    source=SOURCE,
                    updated_at=datetime(2026, 9, 15, 8, 0, 0),
                )
            )
        if work_date == date(2026, 9, 3):
            session.add(
                InvIssueRow(
                    work_date=work_date,
                    schedule_dept=DEPT,
                    dest="QC",
                    item_code="P1",
                    qty_board=80,
                    kg_per_board_snap=_kg(items, "P1"),
                    note="品控留样",
                    created_by=SOURCE,
                )
            )
            session.add(
                InvIssueRow(
                    work_date=work_date,
                    schedule_dept=DEPT,
                    dest="RD",
                    item_code="P5",
                    qty_board=40,
                    kg_per_board_snap=_kg(items, "P5"),
                    note="研发试做",
                    created_by=SOURCE,
                )
            )
        if work_date == date(2026, 9, 8):
            session.add(
                InvIssueRow(
                    work_date=work_date,
                    schedule_dept=DEPT,
                    dest="SALES",
                    item_code="P4",
                    qty_board=60,
                    kg_per_board_snap=_kg(items, "P4"),
                    note="业务赠样",
                    created_by=SOURCE,
                )
            )
            session.add(
                InvIssueRow(
                    work_date=work_date,
                    schedule_dept=DEPT,
                    dest="INTERNAL",
                    item_code="P2",
                    qty_board=120,
                    kg_per_board_snap=_kg(items, "P2"),
                    note="内部混装",
                    created_by=SOURCE,
                )
            )

    for work_date in PLAN_ONLY_DAYS:
        for item_code, group_code, base in LINES:
            item = items.get(item_code)
            if item is None:
                continue
            plan = _scale(base, 1.0)
            wo_no = f"{WO_PREFIX}{item_code}-{work_date.strftime('%m%d')}"
            so_no = f"{SO_PREFIX}{item_code}-{work_date.strftime('%m%d')}"
            session.add(
                SoOrderRow(
                    order_no=so_no,
                    customer="一部日报拟真（不进排程池）",
                    sales_name="演示",
                    item_code=item_code,
                    qty_order=str(plan),
                    unit="BOARD",
                    due_date=work_date + timedelta(days=2),
                    customer_level=3,
                    amount="0",
                    is_urgent=False,
                    schedule_phase="DONE",
                    order_source=SOURCE,
                )
            )
            session.add(
                WoRow(
                    wo_no=wo_no,
                    wo_type="FINISHED",
                    source_order_no=so_no,
                    item_code=item_code,
                    group_code=group_code,
                    dept=DEPT,
                    qty_order=str(plan),
                    qty_board_plan=plan,
                    due_date=work_date + timedelta(days=2),
                    plan_start=work_date,
                    plan_end=work_date,
                    earliest_start=work_date,
                    crew_plan=8,
                    status="RELEASED",
                    plan_version=DEMO_PLAN_VERSION,
                )
            )
            session.add(
                WoTaskRow(
                    wo_no=wo_no,
                    dept=DEPT,
                    group_code=group_code,
                    task_date=work_date,
                    qty_board=plan,
                    hours_wall="8",
                    hours_man="24",
                    crew_plan=8,
                    seq=1,
                    plan_version=DEMO_PLAN_VERSION,
                )
            )
            planted_lines += 1
    session.flush()
    return {"task_days": len(REPORTED_DAYS) + len(PLAN_ONLY_DAYS), "lines": planted_lines}


def _kg(items: dict[str, MdItemRow], code: str) -> str | None:
    item = items.get(code)
    if item is None or item.kg_per_board is None:
        return None
    return str(item.kg_per_board)


def _q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def ensure_dept1_stats_seed(session: Session) -> dict:
    stored = _stored_version(session)
    n_rep = int(
        session.scalar(
            select(func.count())
            .select_from(ProdTimeReportRow)
            .where(ProdTimeReportRow.plan_version == DEMO_PLAN_VERSION)
        )
        or 0
    )
    if stored == STATS_VERSION and n_rep > 0:
        return {"version": STATS_VERSION, "planted": False, "task_days": len(REPORTED_DAYS)}
    _clear_demo(session)
    planted = _plant(session)
    _set_version(session, STATS_VERSION)
    session.flush()
    return {"version": STATS_VERSION, "planted": True, **planted}
