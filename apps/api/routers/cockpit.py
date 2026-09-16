"""Phase 7 驾驶舱 + 职能模块摘要。"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db.cockpit_metrics import cockpit_snapshot
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


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
    def proj_summary(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
        _role(x_demo_role)
        return {
            "code": 0,
            "message": "",
            "data": {
                "active_projects": 4,
                "risk_projects": 1,
                "note": "M7 项目交付摘要",
            },
        }
