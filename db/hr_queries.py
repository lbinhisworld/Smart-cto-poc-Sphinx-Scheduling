"""M1 人事 · 花名册与考勤明细查询。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.tables import HrAttendancePunchRow, HrEmployeeRow

DEPARTMENTS_ORDER = ("生产一部", "生产二部", "模具组", "浇注组", "手工组", "行政人事", "销售中心")
DEFAULT_REMIND_DAYS = 30
ANCHOR_TODAY = date(2026, 9, 15)

RENEWAL_STATUS_LABELS = {
    "OK": "正常",
    "DUE_SOON": "一个月内续签",
    "EXPIRED": "续签过期",
}


def contract_status_for(end: date | None, *, today: date, remind_days: int) -> str:
    if end is None:
        return "OK"
    days = (end - today).days
    if days < 0:
        return "EXPIRED"
    if days <= remind_days:
        return "DUE_SOON"
    return "OK"


def days_until_renewal(end: date | None, *, today: date) -> int | None:
    if end is None:
        return None
    return (end - today).days


def renewal_status_label(status: str) -> str:
    return RENEWAL_STATUS_LABELS.get(status, status)


def _employee_public(e: HrEmployeeRow, *, today: date) -> dict:
    remind = e.contract_remind_days or DEFAULT_REMIND_DAYS
    status = contract_status_for(e.contract_end, today=today, remind_days=remind)
    return {
        "emp_no": e.emp_no,
        "name": e.name,
        "department": e.department,
        "position": e.position,
        "status": e.status,
        "hired_date": e.hired_date.isoformat() if e.hired_date else None,
        "employee_kind": e.employee_kind,
        "is_team_leader": e.is_team_leader,
        "schedule_dept": e.schedule_dept,
        "group_code": e.group_code,
        "contract_start": e.contract_start.isoformat() if e.contract_start else None,
        "contract_end": e.contract_end.isoformat() if e.contract_end else None,
        "contract_remind_days": remind,
        "contract_status": status,
        "renewal_status_label": renewal_status_label(status),
        "days_until_renewal": days_until_renewal(e.contract_end, today=today),
    }


def list_employees(
    session: Session,
    *,
    department: str | None = None,
    today: date | None = None,
) -> list[dict]:
    anchor = today or ANCHOR_TODAY
    q = select(HrEmployeeRow).order_by(HrEmployeeRow.department, HrEmployeeRow.emp_no)
    rows = session.scalars(q).all()
    out: list[dict] = []
    for e in rows:
        if department and e.department != department:
            continue
        out.append(_employee_public(e, today=anchor))
    return out


def list_contract_reminders(session: Session, *, today: date) -> list[dict]:
    out: list[dict] = []
    for row in list_employees(session, today=today):
        if row["contract_status"] not in ("DUE_SOON", "EXPIRED"):
            continue
        label = renewal_status_label(row["contract_status"])
        days = row["days_until_renewal"]
        if days is None:
            countdown = ""
        elif days >= 0:
            countdown = f"还有 {days} 天"
        else:
            countdown = f"已过期 {abs(days)} 天"
        out.append(
            {
                "emp_no": row["emp_no"],
                "name": row["name"],
                "contract_end": row["contract_end"],
                "contract_status": row["contract_status"],
                "title": f"{label} · {row['emp_no']} {row['name']}",
                "detail": f"到期日 {row['contract_end']} · {countdown}".rstrip(" ·"),
                "priority": "high",
            }
        )
    return out


def employee_detail(session: Session, emp_no: str, *, today: date | None = None) -> dict | None:
    e = session.get(HrEmployeeRow, emp_no)
    if e is None:
        return None
    recent = session.scalars(
        select(HrAttendancePunchRow)
        .where(HrAttendancePunchRow.emp_no == emp_no)
        .order_by(HrAttendancePunchRow.punch_at.desc())
        .limit(10)
    ).all()
    data = _employee_public(e, today=today or ANCHOR_TODAY)
    data["recent_punches"] = [
        {
            "id": p.id,
            "punch_at": p.punch_at.isoformat(sep=" ", timespec="seconds"),
            "punch_type": p.punch_type,
            "device_name": p.device_name,
            "synced_at": p.synced_at.isoformat(sep=" ", timespec="seconds"),
        }
        for p in recent
    ]
    return data


def list_attendance_punches(
    session: Session,
    *,
    work_date: date | None = None,
    emp_no: str | None = None,
) -> list[dict]:
    q = select(HrAttendancePunchRow).order_by(HrAttendancePunchRow.punch_at.desc())
    rows = session.scalars(q).all()
    emp_cache: dict[str, HrEmployeeRow | None] = {}
    out: list[dict] = []
    for p in rows:
        if emp_no and p.emp_no != emp_no:
            continue
        if work_date:
            if p.punch_at.date() != work_date:
                continue
        if p.emp_no not in emp_cache:
            emp_cache[p.emp_no] = session.get(HrEmployeeRow, p.emp_no)
        emp = emp_cache[p.emp_no]
        out.append(
            {
                "id": p.id,
                "emp_no": p.emp_no,
                "emp_name": emp.name if emp else p.emp_no,
                "department": emp.department if emp else "",
                "punch_at": p.punch_at.isoformat(sep=" ", timespec="seconds"),
                "punch_type": p.punch_type,
                "device_code": p.device_code,
                "device_name": p.device_name,
                "synced_at": p.synced_at.isoformat(sep=" ", timespec="seconds"),
            }
        )
    return out


def hr_summary_metrics(session: Session) -> dict:
    employees = session.scalars(select(HrEmployeeRow)).all()
    active = sum(1 for e in employees if e.status == "ACTIVE")
    dept_counts: dict[str, int] = {}
    for e in employees:
        dept_counts[e.department] = dept_counts.get(e.department, 0) + 1
    ordered_depts = [d for d in DEPARTMENTS_ORDER if d in dept_counts]
    for d in sorted(dept_counts.keys()):
        if d not in ordered_depts:
            ordered_depts.append(d)
    return {
        "headcount": len(employees),
        "active_count": active,
        "departments": ordered_depts,
        "department_counts": dept_counts,
        "note": "M1 人事 · 花名册与考勤机同步（演示）",
    }
