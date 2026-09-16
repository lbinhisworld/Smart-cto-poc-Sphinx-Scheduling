"""M1b 人工成本 · 计划汇总、组×日报工、部门-组成本。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.plan_store import current_plan_version
from db.tables import HrEmployeeRow, HrLaborRateRow, ProdTimeReportRow, WoTaskRow
from shared.labor_math import decimal_hours, labor_cost, variance_pct

WORK_CENTERS: tuple[tuple[str, str, str], ...] = (
    ("FINISHED_DEPT", "MANUAL", "一部·手工组"),
    ("FINISHED_DEPT", "MOLD", "一部·模具组"),
    ("FINISHED_DEPT", "POURING", "一部·浇注组"),
    ("SEMI_DEPT", "MANUAL", "二部·手工组"),
    ("SEMI_DEPT", "MOLD", "二部·模具组"),
    ("SEMI_DEPT", "POURING", "二部·浇注组"),
)


def display_dept(schedule_dept: str) -> str:
    return "生产一部" if schedule_dept == "FINISHED_DEPT" else "生产二部"


def leader_scope(session: Session, role: str) -> tuple[str, str] | None:
    """演示：TEAM_LEADER 固定对应 E2001 王强 · 一部手工组。"""
    if role != "TEAM_LEADER":
        return None
    emp = session.get(HrEmployeeRow, "E2001")
    if emp and emp.schedule_dept and emp.group_code:
        return emp.schedule_dept, emp.group_code
    return None


def can_manage_group(role: str, scope: tuple[str, str] | None, schedule_dept: str, group_code: str) -> bool:
    if role in ("GM", "PMC"):
        return True
    if role == "TEAM_LEADER" and scope == (schedule_dept, group_code):
        return True
    return False


def _rate_for_group(session: Session, schedule_dept: str, group_code: str) -> Decimal:
    row = session.scalars(
        select(HrLaborRateRow)
        .where(HrLaborRateRow.schedule_dept == schedule_dept)
        .where(HrLaborRateRow.group_code == group_code)
        .order_by(HrLaborRateRow.effective_from.desc())
    ).first()
    if row is None:
        return Decimal("0")
    return decimal_hours(row.rate_per_man_hour)


def sum_planned_man_hours(
    session: Session,
    *,
    plan_version: int,
    work_date: date,
    schedule_dept: str,
    group_code: str,
) -> Decimal:
    total = session.scalar(
        select(func.coalesce(func.sum(WoTaskRow.hours_man), 0))
        .where(WoTaskRow.plan_version == plan_version)
        .where(WoTaskRow.task_date == work_date)
        .where(WoTaskRow.dept == schedule_dept)
        .where(WoTaskRow.group_code == group_code)
    )
    return decimal_hours(total or 0)


def planned_man_hours_by_cell(
    session: Session,
    *,
    plan_version: int,
    date_from: date,
    date_to: date,
) -> list[dict]:
    rows = session.execute(
        select(
            WoTaskRow.dept,
            WoTaskRow.group_code,
            WoTaskRow.task_date,
            func.sum(WoTaskRow.hours_man),
        )
        .where(WoTaskRow.plan_version == plan_version)
        .where(WoTaskRow.task_date >= date_from)
        .where(WoTaskRow.task_date <= date_to)
        .group_by(WoTaskRow.dept, WoTaskRow.group_code, WoTaskRow.task_date)
    ).all()
    out: list[dict] = []
    for dept, group, task_date, hours_sum in rows:
        h = decimal_hours(hours_sum or 0)
        rate = _rate_for_group(session, dept, group)
        out.append(
            {
                "work_date": task_date.isoformat(),
                "schedule_dept": dept,
                "group_code": group,
                "group_label": next(
                    (lbl for d, g, lbl in WORK_CENTERS if d == dept and g == group),
                    group,
                ),
                "display_dept": display_dept(dept),
                "hours_man_planned": float(h),
                "cost_planned": float(labor_cost(h, rate)),
            }
        )
    return sorted(out, key=lambda x: (x["work_date"], x["schedule_dept"], x["group_code"]))


def list_tasks_for_cell(
    session: Session,
    *,
    plan_version: int,
    work_date: date,
    schedule_dept: str,
    group_code: str,
) -> list[dict]:
    rows = session.scalars(
        select(WoTaskRow)
        .where(WoTaskRow.plan_version == plan_version)
        .where(WoTaskRow.task_date == work_date)
        .where(WoTaskRow.dept == schedule_dept)
        .where(WoTaskRow.group_code == group_code)
        .order_by(WoTaskRow.wo_no, WoTaskRow.seq)
    ).all()
    from db.tables import WoRow

    out: list[dict] = []
    for r in rows:
        wo = session.get(WoRow, r.wo_no)
        done = int(getattr(wo, "qty_board_done", 0) or 0) if wo else 0
        plan = int(wo.qty_board_plan) if wo else r.qty_board
        out.append(
            {
                "task_id": r.task_id,
                "wo_no": r.wo_no,
                "task_date": r.task_date.isoformat(),
                "qty_board": r.qty_board,
                "qty_board_plan": plan,
                "qty_board_done": done,
                "qty_board_remain": max(0, plan - done),
                "wo_status": wo.status if wo else None,
                "hours_man": float(decimal_hours(r.hours_man)),
                "hours_wall": float(decimal_hours(r.hours_wall)),
                "crew_plan": r.crew_plan,
            }
        )
    return out


def _hours_cap_fields(session: Session, work_date: date, schedule_dept: str, group_code: str) -> dict:
    from db.attendance_capacity import attendance_hours_cap

    cap = attendance_hours_cap(
        session, work_date=work_date, schedule_dept=schedule_dept, group_code=group_code
    )
    return {"hours_cap": float(cap) if cap is not None else None}


def _assert_hours_within_attendance(
    session: Session,
    *,
    work_date: date,
    schedule_dept: str,
    group_code: str,
    hours_man_actual: Decimal,
) -> None:
    from db.attendance_capacity import attendance_hours_cap

    cap = attendance_hours_cap(
        session, work_date=work_date, schedule_dept=schedule_dept, group_code=group_code
    )
    if cap is None:
        raise ValueError("当日无考勤记录，不能报工")
    if decimal_hours(hours_man_actual) > cap:
        raise ValueError(f"报工人·时超过考勤上限 {cap}（实到人数 × 日工时）")


def _report_to_dict(r: ProdTimeReportRow, session: Session) -> dict:
    rate = _rate_for_group(session, r.schedule_dept, r.group_code)
    planned = decimal_hours(r.hours_man_planned)
    actual = decimal_hours(r.hours_man_actual) if r.hours_man_actual is not None else Decimal("0")
    lbl = next(
        (x[2] for x in WORK_CENTERS if x[0] == r.schedule_dept and x[1] == r.group_code),
        r.group_code,
    )
    return {
        "id": r.id,
        "work_date": r.work_date.isoformat(),
        "schedule_dept": r.schedule_dept,
        "group_code": r.group_code,
        "group_label": lbl,
        "display_dept": display_dept(r.schedule_dept),
        "plan_version": r.plan_version,
        "hours_man_planned": float(planned),
        "hours_man_actual": float(actual) if r.hours_man_actual is not None else None,
        "headcount_actual": r.headcount_actual,
        "status": r.status,
        "reported_by": r.reported_by,
        "confirmed_at": r.confirmed_at.isoformat(sep=" ", timespec="seconds") if r.confirmed_at else None,
        "note": r.note,
        "rate_per_man_hour": float(rate),
        "cost_planned": float(labor_cost(planned, rate)),
        "cost_actual": float(labor_cost(actual, rate)) if r.status == "CONFIRMED" else None,
        **_hours_cap_fields(session, r.work_date, r.schedule_dept, r.group_code),
    }


def list_time_reports(
    session: Session,
    *,
    work_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    q = select(ProdTimeReportRow).order_by(
        ProdTimeReportRow.work_date.desc(),
        ProdTimeReportRow.schedule_dept,
        ProdTimeReportRow.group_code,
    )
    rows = session.scalars(q).all()
    out: list[dict] = []
    for r in rows:
        if work_date and r.work_date != work_date:
            continue
        if date_from and r.work_date < date_from:
            continue
        if date_to and r.work_date > date_to:
            continue
        out.append(_report_to_dict(r, session))
    return out


def upsert_time_report(
    session: Session,
    *,
    work_date: date,
    schedule_dept: str,
    group_code: str,
    hours_man_actual: Decimal | None,
    headcount_actual: int | None,
    note: str,
    reported_by: str,
    plan_version: int | None = None,
) -> dict:
    pv = plan_version or current_plan_version(session)
    if pv <= 0:
        raise ValueError("尚无已发布计划版本，请先排程发布")
    planned = sum_planned_man_hours(
        session,
        plan_version=pv,
        work_date=work_date,
        schedule_dept=schedule_dept,
        group_code=group_code,
    )
    row = session.scalars(
        select(ProdTimeReportRow)
        .where(ProdTimeReportRow.work_date == work_date)
        .where(ProdTimeReportRow.schedule_dept == schedule_dept)
        .where(ProdTimeReportRow.group_code == group_code)
        .where(ProdTimeReportRow.plan_version == pv)
    ).first()
    if row is None:
        row = ProdTimeReportRow(
            work_date=work_date,
            schedule_dept=schedule_dept,
            group_code=group_code,
            plan_version=pv,
            hours_man_planned=str(planned),
            status="DRAFT",
            reported_by=reported_by,
        )
        session.add(row)
    else:
        row.hours_man_planned = str(planned)
        row.reported_by = reported_by
    if hours_man_actual is not None:
        actual = decimal_hours(hours_man_actual)
        _assert_hours_within_attendance(
            session,
            work_date=work_date,
            schedule_dept=schedule_dept,
            group_code=group_code,
            hours_man_actual=actual,
        )
        row.hours_man_actual = str(actual)
    if headcount_actual is not None:
        row.headcount_actual = headcount_actual
    row.note = note or row.note
    session.flush()
    return _report_to_dict(row, session)


def confirm_time_report(session: Session, report_id: int, *, reported_by: str) -> dict:
    row = session.get(ProdTimeReportRow, report_id)
    if row is None:
        raise KeyError(report_id)
    if row.hours_man_actual is None:
        raise ValueError("请先填写实际总人·时")
    _assert_hours_within_attendance(
        session,
        work_date=row.work_date,
        schedule_dept=row.schedule_dept,
        group_code=row.group_code,
        hours_man_actual=decimal_hours(row.hours_man_actual),
    )
    row.hours_man_planned = str(
        sum_planned_man_hours(
            session,
            plan_version=row.plan_version,
            work_date=row.work_date,
            schedule_dept=row.schedule_dept,
            group_code=row.group_code,
        )
    )
    row.status = "CONFIRMED"
    row.reported_by = reported_by
    row.confirmed_at = datetime.now(UTC).replace(tzinfo=None)
    session.flush()
    return _report_to_dict(row, session)


def labor_cost_summary(session: Session, *, date_from: date, date_to: date) -> dict:
    pv = current_plan_version(session)
    planned_cells = planned_man_hours_by_cell(
        session, plan_version=pv, date_from=date_from, date_to=date_to
    ) if pv > 0 else []
    reports = {
        (r.work_date, r.schedule_dept, r.group_code): r
        for r in session.scalars(select(ProdTimeReportRow).where(ProdTimeReportRow.status == "CONFIRMED")).all()
    }
    by_group: dict[tuple[str, str], dict] = {}
    for cell in planned_cells:
        wd = date.fromisoformat(cell["work_date"])
        key = (cell["schedule_dept"], cell["group_code"])
        g = by_group.setdefault(
            key,
            {
                "schedule_dept": cell["schedule_dept"],
                "group_code": cell["group_code"],
                "group_label": cell["group_label"],
                "display_dept": cell["display_dept"],
                "hours_planned": Decimal("0"),
                "hours_actual": Decimal("0"),
                "cost_planned": Decimal("0"),
                "cost_actual": Decimal("0"),
            },
        )
        g["hours_planned"] += decimal_hours(cell["hours_man_planned"])
        g["cost_planned"] += decimal_hours(cell["cost_planned"])
        rep = reports.get((wd, cell["schedule_dept"], cell["group_code"]))
        if rep and rep.hours_man_actual is not None:
            h = decimal_hours(rep.hours_man_actual)
            rate = _rate_for_group(session, rep.schedule_dept, rep.group_code)
            g["hours_actual"] += h
            g["cost_actual"] += labor_cost(h, rate)

    rows: list[dict] = []
    for g in by_group.values():
        hp = g["hours_planned"]
        ha = g["hours_actual"]
        cp = g["cost_planned"]
        ca = g["cost_actual"]
        vp = variance_pct(hp, ha)
        rows.append(
            {
                "display_dept": g["display_dept"],
                "schedule_dept": g["schedule_dept"],
                "group_code": g["group_code"],
                "group_label": g["group_label"],
                "hours_planned": float(hp),
                "hours_actual": float(ha),
                "cost_planned": float(cp.quantize(Decimal("0.01"))),
                "cost_actual": float(ca.quantize(Decimal("0.01"))),
                "variance_pct": float(vp) if vp is not None else None,
            }
        )
    rows.sort(key=lambda x: (x["display_dept"], x["group_code"]))
    total_planned = sum(r["cost_planned"] for r in rows)
    total_actual = sum(r["cost_actual"] for r in rows)
    return {
        "plan_version": pv,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "totals": {
            "cost_planned": total_planned,
            "cost_actual": total_actual,
            "variance_pct": float(variance_pct(decimal_hours(total_planned), decimal_hours(total_actual)))
            if total_planned
            else None,
        },
        "rows": rows,
    }


def time_report_grid(
    session: Session,
    *,
    work_date: date,
    plan_version: int | None = None,
) -> list[dict]:
    """组×日一行：计划 + 已有报工状态（供班组长页）。"""
    pv = plan_version or current_plan_version(session)
    existing = {
        (r.schedule_dept, r.group_code): r
        for r in session.scalars(
            select(ProdTimeReportRow)
            .where(ProdTimeReportRow.work_date == work_date)
            .where(ProdTimeReportRow.plan_version == pv)
        ).all()
    }
    grid: list[dict] = []
    for dept, group, lbl in WORK_CENTERS:
        planned = sum_planned_man_hours(session, plan_version=pv, work_date=work_date, schedule_dept=dept, group_code=group) if pv > 0 else Decimal("0")
        grid.append(
            _cell_row(
                session,
                work_date=work_date,
                schedule_dept=dept,
                group_code=group,
                group_label=lbl,
                plan_version=pv,
                planned=planned,
                report=existing.get((dept, group)),
            )
        )
    return grid


def _cell_row(
    session: Session,
    *,
    work_date: date,
    schedule_dept: str,
    group_code: str,
    group_label: str,
    plan_version: int,
    planned: Decimal,
    report: ProdTimeReportRow | None,
) -> dict:
    if report:
        return _report_to_dict(report, session)
    rate = _rate_for_group(session, schedule_dept, group_code)
    return {
        "id": None,
        "work_date": work_date.isoformat(),
        "schedule_dept": schedule_dept,
        "group_code": group_code,
        "group_label": group_label,
        "display_dept": display_dept(schedule_dept),
        "plan_version": plan_version,
        "hours_man_planned": float(planned),
        "hours_man_actual": None,
        "headcount_actual": None,
        "status": "NONE",
        "reported_by": "",
        "confirmed_at": None,
        "note": "",
        "rate_per_man_hour": float(rate),
        "cost_planned": float(labor_cost(planned, rate)),
        "cost_actual": None,
        **_hours_cap_fields(session, work_date, schedule_dept, group_code),
    }


def time_report_timeline(
    session: Session,
    *,
    today: date,
    plan_version: int | None = None,
    scope: tuple[str, str] | None = None,
) -> dict:
    """有计划的组×日按日期分组；未确认在 open，已确认进 done。"""
    pv = plan_version or current_plan_version(session)
    empty = {"plan_version": pv, "today": today.isoformat(), "open": [], "done": []}
    if pv <= 0:
        return empty

    bounds = session.execute(
        select(func.min(WoTaskRow.task_date), func.max(WoTaskRow.task_date)).where(
            WoTaskRow.plan_version == pv
        )
    ).one()
    date_from, date_to = bounds
    if date_from is None or date_to is None:
        return empty

    cells = planned_man_hours_by_cell(
        session, plan_version=pv, date_from=date_from, date_to=date_to
    )
    reports = {
        (r.work_date, r.schedule_dept, r.group_code): r
        for r in session.scalars(
            select(ProdTimeReportRow).where(ProdTimeReportRow.plan_version == pv)
        ).all()
    }

    by_date: dict[date, list[dict]] = {}
    for cell in cells:
        if cell["hours_man_planned"] <= 0:
            continue
        dept, group = cell["schedule_dept"], cell["group_code"]
        if scope is not None and scope != (dept, group):
            continue
        wd = date.fromisoformat(cell["work_date"])
        lbl = cell["group_label"]
        planned = decimal_hours(cell["hours_man_planned"])
        row = _cell_row(
            session,
            work_date=wd,
            schedule_dept=dept,
            group_code=group,
            group_label=lbl,
            plan_version=pv,
            planned=planned,
            report=reports.get((wd, dept, group)),
        )
        by_date.setdefault(wd, []).append(row)

    open_nodes: list[dict] = []
    done_nodes: list[dict] = []
    for wd in sorted(by_date):
        rows = by_date[wd]
        if wd < today:
            bucket = "overdue"
        elif wd == today:
            bucket = "today"
        else:
            bucket = "upcoming"
        all_confirmed = all(r["status"] == "CONFIRMED" for r in rows)
        node = {
            "work_date": wd.isoformat(),
            "bucket": bucket,
            "hours_planned": round(sum(r["hours_man_planned"] for r in rows), 4),
            "all_confirmed": all_confirmed,
            "rows": rows,
        }
        (done_nodes if all_confirmed else open_nodes).append(node)

    bucket_rank = {"overdue": 0, "today": 1, "upcoming": 2}
    open_nodes.sort(key=lambda n: (bucket_rank[n["bucket"]], n["work_date"]))
    return {"plan_version": pv, "today": today.isoformat(), "open": open_nodes, "done": done_nodes}
