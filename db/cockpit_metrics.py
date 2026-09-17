"""管理驾驶舱指标（Phase 7 演示）。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from datetime import date

from db.plan_store import current_plan_version
from db.product_labor_cost import planned_labor_cost_by_product
from db.qc_metrics import qc_summary
from db.qc_seed import ensure_qc_seed
from db.tables import CrmOpportunityRow, CrmSampleRow, SoOrderRow, WoRow


def cockpit_snapshot(session: Session, *, today_iso: str = "2026-09-15") -> dict:
    order_total = session.scalar(select(func.count()).select_from(SoOrderRow)) or 0
    pending = session.scalar(
        select(func.count())
        .select_from(SoOrderRow)
        .where(SoOrderRow.schedule_phase == "PENDING")
    ) or 0
    in_sched = session.scalar(
        select(func.count())
        .select_from(SoOrderRow)
        .where(SoOrderRow.schedule_phase == "IN_SCHEDULING")
    ) or 0
    near_due = session.scalar(
        select(func.count())
        .select_from(SoOrderRow)
        .where(SoOrderRow.due_date <= __import__("datetime").date.fromisoformat("2026-09-22"))
    ) or 0
    opp_total = session.scalar(select(func.count()).select_from(CrmOpportunityRow)) or 0
    sample_active = session.scalar(
        select(func.count())
        .select_from(CrmSampleRow)
        .where(CrmSampleRow.current_stage != "结案")
    ) or 0
    ver = current_plan_version(session)
    wo_released = 0
    if ver > 0:
        wo_released = session.scalar(
            select(func.count()).select_from(WoRow).where(WoRow.plan_version == ver)
        ) or 0
    labor_products: list[dict] = []
    labor_totals: dict = {"hours_man": 0.0, "cost_planned": 0.0}
    if ver > 0:
        lp = planned_labor_cost_by_product(session, plan_version=ver)
        labor_totals = lp.get("totals") or labor_totals
        labor_products = (lp.get("products") or [])[:5]

    ensure_qc_seed(session)
    qc = qc_summary(session, today=date.fromisoformat(today_iso))

    return {
        "today": today_iso,
        "orders": {"total": order_total, "pending": pending, "in_scheduling": in_sched, "near_due_7d": near_due},
        "crm": {"opportunities": opp_total, "active_samples": sample_active},
        "qc": qc,
        "production": {"plan_version": ver, "wo_count": wo_released},
        "labor_cost": {
            "plan_version": ver,
            "totals": labor_totals,
            "top_products": labor_products,
            "note": "计划人工成本（人·时×标准单价），按成品品项汇总",
        },
        "legacy_excel_sheets": 20,
        "note": "现状对照：Excel 一表三用 vs 一体化排程+CRM",
    }
