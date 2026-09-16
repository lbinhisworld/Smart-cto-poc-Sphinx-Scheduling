"""M1 人事：花名册、考勤打卡明细。"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

from db.attendance_capacity import (
    group_attendance_summary,
    list_group_attendance,
    sync_attendance_from_punches,
    upsert_manual_attendance,
)
from db.hr_queries import employee_detail, hr_summary_metrics, list_attendance_punches, list_employees
from db.hr_seed import ensure_hr_seed
from shared.auth import user_for_role


class ManualAttendanceBody(BaseModel):
    schedule_dept: str
    group_code: str
    work_date: date
    headcount_present: int = Field(ge=0, le=99)


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def register_hr(app, get_db):
    @app.get("/api/hr/employees")
    def hr_employees(
        department: str | None = None,
        today: date | None = Query(default=None),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        return {
            "code": 0,
            "message": "",
            "data": list_employees(db, department=department, today=today),
        }

    @app.get("/api/hr/employees/{emp_no}")
    def hr_employee_one(
        emp_no: str,
        today: date | None = Query(default=None),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        data = employee_detail(db, emp_no, today=today)
        if data is None:
            raise HTTPException(status_code=404, detail="员工不存在")
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/hr/attendance/punches")
    def hr_attendance_punches(
        work_date: date | None = Query(default=None),
        emp_no: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        return {
            "code": 0,
            "message": "",
            "data": list_attendance_punches(db, work_date=work_date, emp_no=emp_no),
        }

    @app.get("/api/hr/attendance/group-summary")
    def hr_attendance_group_summary(
        work_date: date = Query(...),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        return {
            "code": 0,
            "message": "",
            "data": group_attendance_summary(db, work_date=work_date),
        }

    @app.post("/api/hr/attendance/sync-to-scheduling")
    def hr_attendance_sync(
        work_date: date = Query(...),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        rows = sync_attendance_from_punches(db, work_date)
        db.commit()
        return {
            "code": 0,
            "message": "已写入组×日出勤，下次倒排/试算将按实到人数约束产能",
            "data": rows,
        }

    @app.post("/api/hr/attendance/manual")
    def hr_attendance_manual(
        body: ManualAttendanceBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        row = upsert_manual_attendance(
            db,
            schedule_dept=body.schedule_dept,
            group_code=body.group_code,
            work_date=body.work_date,
            headcount_present=body.headcount_present,
        )
        db.commit()
        return {"code": 0, "message": "", "data": row}

    @app.get("/api/hr/attendance/scheduling-overlay")
    def hr_attendance_overlay(
        work_date: date = Query(...),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {
            "code": 0,
            "message": "",
            "data": list_group_attendance(db, work_date=work_date),
        }

    @app.get("/api/hr/summary")
    def hr_summary(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        return {"code": 0, "message": "", "data": hr_summary_metrics(db)}
