"""Phase 7 驾驶舱 + 职能模块摘要。"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.cockpit_metrics import cockpit_snapshot
from db.qc_ledgers import production_qc_alerts
from db.demo_crm_seed import ensure_demo_crm
from db.project_board import (
    ProjectBoardError,
    ensure_project_board,
    project_board,
    project_summary,
    set_step_date,
    stage_detail,
)
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def _gm(x_demo_role: str | None) -> str:
    role = _role(x_demo_role)
    if role != "GM":
        raise HTTPException(status_code=403, detail="仅总经理可查看项目大盘")
    return role


class ProjectStepDate(BaseModel):
    stage_code: str
    step_no: int
    event_date: str


def _load_projects(db: Session) -> None:
    ensure_demo_crm(db)
    ensure_project_board(db)


def register_cockpit(app, get_db):
    @app.get("/api/cockpit/snapshot")
    def snapshot(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {"code": 0, "message": "", "data": cockpit_snapshot(db)}

    @app.get("/api/modules/hr/summary")
    def hr_summary_legacy(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        from datetime import date

        from db.hr_queries import hr_summary_metrics
        from db.hr_seed import ensure_hr_seed
        from db.labor_cost_queries import labor_cost_summary

        ensure_hr_seed(db)
        metrics = hr_summary_metrics(db)
        labor = labor_cost_summary(
            db,
            date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 30),
        )
        totals = labor.get("totals") or {}
        return {
            "code": 0,
            "message": "",
            "data": {
                **metrics,
                "attendance_rate_pct": 97,
                "open_violations": 2,
                "labor_cost_mtd": {
                    "cost_planned": totals.get("cost_planned", 0),
                    "cost_actual": totals.get("cost_actual", 0),
                    "variance_pct": totals.get("variance_pct"),
                    "plan_version": labor.get("plan_version", 0),
                },
            },
        }

    @app.get("/api/modules/production/summary")
    def prod_summary(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        snap = cockpit_snapshot(db)
        return {
            "code": 0,
            "message": "",
            "data": {
                "plan_version": snap["production"]["plan_version"],
                "wo_count": snap["production"]["wo_count"],
                "sph_review_pending": 3,
                "qc_alerts": production_qc_alerts(db, limit=8),
                "note": "M5 生产运营摘要",
            },
        }

    @app.get("/api/modules/finance/summary")
    def fin_summary(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
        _role(x_demo_role)
        return {
            "code": 0,
            "message": "",
            "data": {
                "margin_alert_orders": 1,
                "cost_locked_pct": 88,
                "note": "M6 财务摘要（不含费用政策模块）",
            },
        }

    @app.get("/api/modules/project/summary")
    def proj_summary(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _gm(x_demo_role)
        _load_projects(db)
        return {"code": 0, "message": "", "data": project_summary(db)}

    @app.get("/api/modules/project/board")
    def proj_board(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _gm(x_demo_role)
        _load_projects(db)
        return {"code": 0, "message": "", "data": project_board(db)}

    @app.get("/api/modules/project/{project_code}/stages/{stage_code}")
    def proj_stage(
        project_code: str,
        stage_code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _gm(x_demo_role)
        _load_projects(db)
        data = stage_detail(db, project_code, stage_code)
        if data is None:
            raise HTTPException(status_code=404, detail="项目或环节不存在")
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/modules/project/{project_code}/steps")
    def proj_set_step(
        project_code: str,
        body: ProjectStepDate,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _gm(x_demo_role)
        _load_projects(db)
        try:
            data = set_step_date(db, project_code, body.stage_code, body.step_no, body.event_date)
        except ProjectBoardError as exc:
            message = str(exc)
            status = 404 if message in {"项目不存在", "步骤不存在", "未知环节"} else 400
            raise HTTPException(status_code=status, detail=message) from exc
        return {"code": 0, "message": "", "data": data}
