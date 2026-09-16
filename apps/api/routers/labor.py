"""M1b 班组长报工 + 计划人时查询。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.hr_seed import ensure_hr_seed
from db.labor_cost_queries import (
    can_manage_group,
    confirm_time_report,
    labor_cost_summary,
    leader_scope,
    list_tasks_for_cell,
    list_time_reports,
    planned_man_hours_by_cell,
    time_report_grid,
    time_report_timeline,
    upsert_time_report,
)
from db.plan_store import current_plan_version
from db.product_labor_cost import planned_labor_cost_by_product, product_labor_for_item
from db.qty_carryover import confirm_wo_qty, list_pending_rolls, resolve_roll, wo_qty_progress
from db.tables import ProdTimeReportRow, WoRow
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


class TimeReportBody(BaseModel):
    work_date: date
    schedule_dept: str
    group_code: str
    hours_man_actual: float | None = None
    headcount_actual: int | None = None
    note: str = ""
    plan_version: int | None = None


class QtyConfirmBody(BaseModel):
    qty_board_done: int = Field(..., ge=0)
    work_date: date | None = None


class QtyResolveBody(BaseModel):
    action: str
    target_order_no: str | None = None
    today: date | None = None


def register_labor(app, get_db):
    @app.get("/api/labor/planned")
    def labor_planned(
        date_from: date,
        date_to: date,
        plan_version: int | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC", "HR", "TEAM_LEADER", "FIN"):
            raise HTTPException(status_code=403, detail="无权查看")
        ensure_hr_seed(db)
        pv = plan_version or current_plan_version(db)
        if pv <= 0:
            return {"code": 0, "message": "", "data": []}
        return {
            "code": 0,
            "message": "",
            "data": planned_man_hours_by_cell(db, plan_version=pv, date_from=date_from, date_to=date_to),
        }

    @app.get("/api/labor/cell-tasks")
    def labor_cell_tasks(
        work_date: date,
        schedule_dept: str,
        group_code: str,
        plan_version: int | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        pv = plan_version or current_plan_version(db)
        if pv <= 0:
            return {"code": 0, "message": "", "data": []}
        return {
            "code": 0,
            "message": "",
            "data": list_tasks_for_cell(
                db,
                plan_version=pv,
                work_date=work_date,
                schedule_dept=schedule_dept,
                group_code=group_code,
            ),
        }

    @app.get("/api/labor/time-reports/grid")
    def labor_time_report_grid(
        work_date: date,
        plan_version: int | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC", "TEAM_LEADER"):
            raise HTTPException(status_code=403, detail="无权查看报工")
        ensure_hr_seed(db)
        return {
            "code": 0,
            "message": "",
            "data": time_report_grid(db, work_date=work_date, plan_version=plan_version),
        }

    @app.get("/api/labor/time-reports/timeline")
    def labor_time_report_timeline(
        today: date | None = None,
        plan_version: int | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC", "TEAM_LEADER"):
            raise HTTPException(status_code=403, detail="无权查看报工")
        ensure_hr_seed(db)
        scope = leader_scope(db, role)
        return {
            "code": 0,
            "message": "",
            "data": time_report_timeline(
                db,
                today=today or date(2026, 9, 15),
                plan_version=plan_version,
                scope=scope,
            ),
        }

    @app.get("/api/labor/time-reports")
    def labor_time_reports_list(
        work_date: date | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC", "TEAM_LEADER", "HR"):
            raise HTTPException(status_code=403, detail="无权查看")
        ensure_hr_seed(db)
        return {
            "code": 0,
            "message": "",
            "data": list_time_reports(db, work_date=work_date, date_from=date_from, date_to=date_to),
        }

    @app.post("/api/labor/time-reports")
    def labor_time_reports_save(
        body: TimeReportBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_hr_seed(db)
        scope = leader_scope(db, role)
        if not can_manage_group(role, scope, body.schedule_dept, body.group_code):
            raise HTTPException(status_code=403, detail="仅可报工本组")
        user = user_for_role(role)
        reported_by = user.name if user else role
        try:
            data = upsert_time_report(
                db,
                work_date=body.work_date,
                schedule_dept=body.schedule_dept,
                group_code=body.group_code,
                hours_man_actual=Decimal(str(body.hours_man_actual)) if body.hours_man_actual is not None else None,
                headcount_actual=body.headcount_actual,
                note=body.note,
                reported_by=reported_by,
                plan_version=body.plan_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/labor/time-reports/{report_id}/confirm")
    def labor_time_reports_confirm(
        report_id: int,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_hr_seed(db)
        row = db.get(ProdTimeReportRow, report_id)
        if row is None:
            raise HTTPException(status_code=404, detail="报工不存在")
        scope = leader_scope(db, role)
        if not can_manage_group(role, scope, row.schedule_dept, row.group_code):
            raise HTTPException(status_code=403, detail="仅可确认本组")
        user = user_for_role(role)
        reported_by = user.name if user else role
        try:
            data = confirm_time_report(db, report_id, reported_by=reported_by)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="报工不存在") from None
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/labor/wos/{wo_no}/qty-progress")
    def labor_wo_qty_progress(
        wo_no: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        try:
            return {"code": 0, "message": "", "data": wo_qty_progress(db, wo_no)}
        except KeyError:
            raise HTTPException(status_code=404, detail="工单不存在") from None

    @app.post("/api/labor/wos/{wo_no}/qty-confirm")
    def labor_wo_qty_confirm(
        wo_no: str,
        body: QtyConfirmBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        wo = db.get(WoRow, wo_no)
        if wo is None:
            raise HTTPException(status_code=404, detail="工单不存在")
        scope = leader_scope(db, role)
        if not can_manage_group(role, scope, wo.dept, wo.group_code):
            raise HTTPException(status_code=403, detail="仅可报工本组")
        user = user_for_role(role)
        reported_by = user.name if user else role
        try:
            data = confirm_wo_qty(
                db,
                wo_no=wo_no,
                qty_board_done=body.qty_board_done,
                reported_by=reported_by,
                work_date=body.work_date,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="工单不存在") from None
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/labor/qty-rolls")
    def labor_qty_rolls(
        status: str | None = "PENDING_CONFIRMATION",
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC", "TEAM_LEADER"):
            raise HTTPException(status_code=403, detail="无权查看")
        return {"code": 0, "message": "", "data": list_pending_rolls(db, status=status)}

    @app.post("/api/labor/qty-rolls/{roll_id}/resolve")
    def labor_qty_rolls_resolve(
        roll_id: int,
        body: QtyResolveBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC"):
            raise HTTPException(status_code=403, detail="仅 PMC/总经理可确认尾数")
        user = user_for_role(role)
        resolved_by = user.name if user else role
        try:
            data = resolve_roll(
                db,
                roll_id=roll_id,
                action=body.action,
                today=body.today or date(2026, 9, 15),
                resolved_by=resolved_by,
                target_order_no=body.target_order_no,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="尾数不存在") from None
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/hr/labor-cost/summary")
    def hr_labor_cost_summary(
        date_from: date,
        date_to: date,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC", "HR", "FIN", "TEAM_LEADER"):
            raise HTTPException(status_code=403, detail="无权查看")
        ensure_hr_seed(db)
        return {"code": 0, "message": "", "data": labor_cost_summary(db, date_from=date_from, date_to=date_to)}

    @app.get("/api/hr/labor-cost/by-product")
    def hr_labor_cost_by_product(
        plan_version: int | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        return {
            "code": 0,
            "message": "",
            "data": planned_labor_cost_by_product(db, plan_version=plan_version),
        }

    @app.get("/api/hr/labor-cost/product/{item_code}")
    def hr_labor_cost_product_one(
        item_code: str,
        plan_version: int | None = None,
        qty: float | None = None,
        unit: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_hr_seed(db)
        data = product_labor_for_item(
            db,
            item_code,
            plan_version=plan_version,
            qty_order=qty,
            unit=unit,
        )
        if data is None:
            raise HTTPException(status_code=404, detail="无已发布计划或品项")
        return {"code": 0, "message": "", "data": data}
