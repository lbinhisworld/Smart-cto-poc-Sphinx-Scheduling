"""M1 人事演示数据（花名册 + 考勤 + 人工单价）。"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.tables import (
    AppSettingRow,
    HrAttendancePunchRow,
    HrEmployeeRow,
    HrLaborRateRow,
    ProdTimeReportRow,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "seed" / "demo_data.json"
HR_VERSION_KEY = "hr_demo_version"


def _load_demo() -> dict:
    if not DEMO_PATH.is_file():
        return {}
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def _stored_hr_version(session: Session) -> str | None:
    row = session.get(AppSettingRow, HR_VERSION_KEY)
    return row.value if row else None


def _set_hr_version(session: Session, version: str) -> None:
    row = session.get(AppSettingRow, HR_VERSION_KEY)
    if row is None:
        session.add(AppSettingRow(key=HR_VERSION_KEY, value=version))
    else:
        row.value = version


def _reload_hr(session: Session, hr: dict) -> dict:
    from db.prod_stats_seed import DEMO_PLAN_VERSION

    session.execute(
        delete(ProdTimeReportRow).where(ProdTimeReportRow.plan_version != DEMO_PLAN_VERSION)
    )
    session.execute(delete(HrLaborRateRow))
    session.execute(delete(HrAttendancePunchRow))
    session.execute(delete(HrEmployeeRow))
    stats = {"employees": 0, "punches": 0, "labor_rates": 0}
    for row in hr.get("employees", []):
        session.add(
            HrEmployeeRow(
                emp_no=row["emp_no"],
                name=row["name"],
                department=row["department"],
                position=row["position"],
                status=row.get("status", "ACTIVE"),
                hired_date=date.fromisoformat(row["hired_date"]) if row.get("hired_date") else None,
                employee_kind=row.get("employee_kind", "STAFF"),
                is_team_leader=bool(row.get("is_team_leader", False)),
                schedule_dept=row.get("schedule_dept"),
                group_code=row.get("group_code"),
                contract_start=date.fromisoformat(row["contract_start"]) if row.get("contract_start") else None,
                contract_end=date.fromisoformat(row["contract_end"]) if row.get("contract_end") else None,
                contract_remind_days=int(row.get("contract_remind_days") or 30),
            )
        )
        stats["employees"] += 1
    for row in hr.get("attendance_punches", []):
        session.add(
            HrAttendancePunchRow(
                emp_no=row["emp_no"],
                punch_at=datetime.fromisoformat(row["punch_at"]),
                punch_type=row["punch_type"],
                device_code=row["device_code"],
                device_name=row["device_name"],
                synced_at=datetime.fromisoformat(row["synced_at"]),
            )
        )
        stats["punches"] += 1
    for row in hr.get("labor_rates", []):
        session.add(
            HrLaborRateRow(
                schedule_dept=row["schedule_dept"],
                group_code=row["group_code"],
                rate_per_man_hour=str(row["rate_per_man_hour"]),
                effective_from=date.fromisoformat(row["effective_from"]),
            )
        )
        stats["labor_rates"] += 1
    return stats


def ensure_hr_seed(session: Session) -> dict:
    data = _load_demo()
    meta = data.get("meta") or {}
    hr = data.get("hr") or {}
    target = str(meta.get("hr_demo_version") or meta.get("demo_version") or "hr-legacy")
    stored = _stored_hr_version(session)
    out: dict = {
        "hr_demo_version": target,
        "resynced": False,
        "employees": 0,
        "punches": 0,
        "labor_rates": 0,
    }
    if stored != target:
        stats = _reload_hr(session, hr)
        out.update(stats)
        out["resynced"] = True
        _set_hr_version(session, target)
    else:
        out["employees"] = int(session.scalar(select(func.count()).select_from(HrEmployeeRow)) or 0)
        out["punches"] = int(session.scalar(select(func.count()).select_from(HrAttendancePunchRow)) or 0)
        out["labor_rates"] = int(session.scalar(select(func.count()).select_from(HrLaborRateRow)) or 0)
    return out
