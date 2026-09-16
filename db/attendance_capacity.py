"""出勤 → 排程日历 overlay（DB 层）。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.labor_cost_queries import WORK_CENTERS
from db.tables import HrAttendancePunchRow, HrEmployeeRow, HrGroupAttendanceRow, MdCapacityCalendarRow
from engine.models import CalendarDay
from shared.labor_math import decimal_hours


def aggregate_punch_headcount(
    session: Session,
    work_date: date,
) -> dict[tuple[str, str], int]:
    """当日有上班打卡的在编员工，按 schedule_dept + group_code 去重计数。"""
    punches = session.scalars(select(HrAttendancePunchRow)).all()
    seen: dict[tuple[str, str], set[str]] = {}
    for p in punches:
        if p.punch_at.date() != work_date:
            continue
        if p.punch_type not in ("IN", "上班", "CHECK_IN"):
            continue
        emp = session.get(HrEmployeeRow, p.emp_no)
        if emp is None or emp.status != "ACTIVE":
            continue
        if not emp.schedule_dept or not emp.group_code:
            continue
        key = (emp.schedule_dept, emp.group_code)
        seen.setdefault(key, set()).add(emp.emp_no)
    return {k: len(v) for k, v in seen.items()}


def _hours_per_day(session: Session, work_date: date, dept: str, group: str) -> Decimal:
    row = session.scalars(
        select(MdCapacityCalendarRow)
        .where(MdCapacityCalendarRow.work_date == work_date)
        .where(MdCapacityCalendarRow.dept == dept)
        .where(MdCapacityCalendarRow.group_code == group)
    ).first()
    if row is not None and row.hours_per_day is not None:
        return decimal_hours(row.hours_per_day)
    return Decimal("8")


def attendance_headcount_present(
    session: Session,
    *,
    work_date: date,
    schedule_dept: str,
    group_code: str,
) -> int | None:
    stored = session.scalars(
        select(HrGroupAttendanceRow)
        .where(HrGroupAttendanceRow.work_date == work_date)
        .where(HrGroupAttendanceRow.schedule_dept == schedule_dept)
        .where(HrGroupAttendanceRow.group_code == group_code)
    ).first()
    if stored is not None:
        return stored.headcount_present
    punch = aggregate_punch_headcount(session, work_date)
    return punch.get((schedule_dept, group_code))


def attendance_hours_cap(
    session: Session,
    *,
    work_date: date,
    schedule_dept: str,
    group_code: str,
) -> Decimal | None:
    present = attendance_headcount_present(
        session,
        work_date=work_date,
        schedule_dept=schedule_dept,
        group_code=group_code,
    )
    if present is None:
        return None
    return decimal_hours(Decimal(present) * _hours_per_day(session, work_date, schedule_dept, group_code))


def list_group_attendance(
    session: Session,
    *,
    work_date: date,
) -> list[dict]:
    rows = session.scalars(
        select(HrGroupAttendanceRow)
        .where(HrGroupAttendanceRow.work_date == work_date)
        .order_by(HrGroupAttendanceRow.schedule_dept, HrGroupAttendanceRow.group_code)
    ).all()
    return [
        {
            "schedule_dept": r.schedule_dept,
            "group_code": r.group_code,
            "work_date": r.work_date.isoformat(),
            "headcount_present": r.headcount_present,
            "source": r.source,
            "updated_at": r.updated_at.isoformat(sep=" ", timespec="seconds"),
        }
        for r in rows
    ]


def sync_attendance_from_punches(session: Session, work_date: date) -> list[dict]:
    """考勤机 → hr_group_attendance（覆盖该日 PUNCH 来源行）。"""
    counts = aggregate_punch_headcount(session, work_date)
    session.execute(
        delete(HrGroupAttendanceRow).where(
            HrGroupAttendanceRow.work_date == work_date,
            HrGroupAttendanceRow.source == "PUNCH",
        )
    )
    now = datetime.now(tz=UTC)
    for (dept, group), n in counts.items():
        session.add(
            HrGroupAttendanceRow(
                schedule_dept=dept,
                group_code=group,
                work_date=work_date,
                headcount_present=n,
                source="PUNCH",
                updated_at=now,
            )
        )
    session.flush()
    return list_group_attendance(session, work_date=work_date)


def upsert_manual_attendance(
    session: Session,
    *,
    schedule_dept: str,
    group_code: str,
    work_date: date,
    headcount_present: int,
) -> dict:
    row = session.scalars(
        select(HrGroupAttendanceRow)
        .where(HrGroupAttendanceRow.schedule_dept == schedule_dept)
        .where(HrGroupAttendanceRow.group_code == group_code)
        .where(HrGroupAttendanceRow.work_date == work_date)
    ).first()
    now = datetime.now(tz=UTC)
    if row is None:
        row = HrGroupAttendanceRow(
            schedule_dept=schedule_dept,
            group_code=group_code,
            work_date=work_date,
            headcount_present=headcount_present,
            source="MANUAL",
            updated_at=now,
        )
        session.add(row)
    else:
        row.headcount_present = headcount_present
        row.source = "MANUAL"
        row.updated_at = now
    session.flush()
    return {
        "schedule_dept": row.schedule_dept,
        "group_code": row.group_code,
        "work_date": row.work_date.isoformat(),
        "headcount_present": row.headcount_present,
        "source": row.source,
    }


def load_attendance_map(
    session: Session,
    date_from: date,
    date_to: date,
) -> dict[tuple[str, str, date], int]:
    rows = session.scalars(
        select(HrGroupAttendanceRow)
        .where(HrGroupAttendanceRow.work_date >= date_from)
        .where(HrGroupAttendanceRow.work_date <= date_to)
    ).all()
    return {
        (r.schedule_dept, r.group_code, r.work_date): r.headcount_present for r in rows
    }


def apply_attendance_to_calendar(
    session: Session,
    calendar: list[CalendarDay],
) -> list[CalendarDay]:
    if not calendar:
        return calendar
    dmin = min(c.work_date for c in calendar)
    dmax = max(c.work_date for c in calendar)
    amap = load_attendance_map(session, dmin, dmax)
    if not amap:
        return calendar
    out: list[CalendarDay] = []
    for c in calendar:
        key = (c.dept.value, c.group_code.value, c.work_date)
        present = amap.get(key)
        if present is None:
            out.append(c)
        else:
            out.append(c.model_copy(update={"headcount_present": present}))
    return out


def _roster_headcount(session: Session, work_date: date, dept: str, group: str) -> int:
    row = session.scalars(
        select(MdCapacityCalendarRow)
        .where(MdCapacityCalendarRow.work_date == work_date)
        .where(MdCapacityCalendarRow.dept == dept)
        .where(MdCapacityCalendarRow.group_code == group)
    ).first()
    return row.headcount if row else 0


def group_attendance_summary(session: Session, *, work_date: date) -> list[dict]:
    stored = {
        (r["schedule_dept"], r["group_code"]): r
        for r in list_group_attendance(session, work_date=work_date)
    }
    punch = aggregate_punch_headcount(session, work_date)
    out: list[dict] = []
    for dept, group, label in WORK_CENTERS:
        roster_hc = _roster_headcount(session, work_date, dept, group)
        row = stored.get((dept, group))
        present = row["headcount_present"] if row else punch.get((dept, group))
        out.append(
            {
                "schedule_dept": dept,
                "group_code": group,
                "group_label": label,
                "work_date": work_date.isoformat(),
                "headcount_roster": roster_hc,
                "headcount_present": present,
                "source": row["source"] if row else ("PUNCH" if present is not None else None),
                "feeds_scheduling": present is not None,
            }
        )
    return out
