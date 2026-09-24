"""演示线 · 重置系统：清空库内全部业务数据，后续仅演示线生成或人工录入。"""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from db.demo_manual_data import set_manual_data_mode
from db.demo_scenario import SCENARIO_LOCK_KEY, reset_order_scenario, set_scenario_lock
from db.demo_crm_seed import DEMO_VERSION_KEY
from db.guided_demo_runs import ACTIVE_RUN_KEY, REPLAY_RUN_KEY
from db.hr_seed import HR_VERSION_KEY
from db.order_lines import LINES_VERSION_KEY
from db.prod_stats_seed import STATS_VERSION_KEY
from db.seed import clear_master_and_orders
from db.tables import (
    AppSettingRow,
    AuditLogRow,
    CrmContractPaymentPlanRow,
    CrmContractRow,
    CrmCustomerRow,
    CrmFieldVisitRow,
    CrmFollowRecordRow,
    CrmLeadPoolRuleRow,
    CrmLeadRow,
    CrmOpportunityRow,
    CrmPaymentReceiptRow,
    CrmQuoteLineRow,
    CrmQuoteRow,
    CrmSalesGoalPeriodRow,
    CrmSalesGoalRow,
    CrmSampleRow,
    CrmSampleStepRow,
    CrmVisitRow,
    DeliveryProjectRow,
    DeliveryProjectStepRow,
    DemoRunFeedbackRow,
    DemoRunRow,
    DemoRunSeedEventRow,
    DemoRunStepSnapshotRow,
    HrAttendancePunchRow,
    HrEmployeeRow,
    HrGroupAttendanceRow,
    HrLaborRateRow,
    InvInboundDailyRow,
    InvIssueRow,
    MdItemRow,
    MdRawMaterialRow,
    MdSupplierRow,
    QcAttachmentRow,
    QcCustomerComplaintRow,
    QcDailyDefectRow,
    QcExceptionEventRow,
    QcExternalAuditRow,
    QcLabExternalRequestRow,
    QcMaterialExceptionRow,
    QcMaterialReceiptRow,
    QcProductTestRow,
    QcSwabPointRow,
    QcSwabTestRow,
    SoOrderRow,
)


def _clear_guided_demo(session: Session) -> dict:
    fb = session.execute(delete(DemoRunFeedbackRow)).rowcount or 0
    seeds = session.execute(delete(DemoRunSeedEventRow)).rowcount or 0
    snaps = session.execute(delete(DemoRunStepSnapshotRow)).rowcount or 0
    runs = session.execute(delete(DemoRunRow)).rowcount or 0
    for key in (ACTIVE_RUN_KEY, REPLAY_RUN_KEY):
        row = session.get(AppSettingRow, key)
        if row is None:
            session.add(AppSettingRow(key=key, value=""))
        else:
            row.value = ""
    return {
        "demo_runs": runs,
        "feedback": fb,
        "seed_events": seeds,
        "snapshots": snaps,
    }


def _clear_crm_and_sales(session: Session) -> None:
    session.execute(delete(CrmFollowRecordRow))
    session.execute(delete(CrmFieldVisitRow))
    session.execute(delete(CrmVisitRow))
    session.execute(delete(CrmLeadRow))
    session.execute(delete(CrmLeadPoolRuleRow))
    session.execute(delete(CrmSalesGoalPeriodRow))
    session.execute(delete(CrmSalesGoalRow))
    session.execute(delete(CrmPaymentReceiptRow))
    session.execute(delete(CrmContractPaymentPlanRow))
    session.execute(delete(CrmContractRow))
    session.execute(delete(CrmQuoteLineRow))
    session.execute(delete(CrmQuoteRow))
    session.execute(delete(CrmSampleStepRow))
    session.execute(delete(CrmSampleRow))
    session.execute(delete(CrmOpportunityRow))
    session.execute(delete(CrmCustomerRow))


def _clear_qc_ledger(session: Session) -> None:
    session.execute(delete(QcAttachmentRow))
    session.execute(delete(QcExceptionEventRow))
    session.execute(delete(QcMaterialExceptionRow))
    session.execute(delete(QcCustomerComplaintRow))
    session.execute(delete(QcLabExternalRequestRow))
    session.execute(delete(QcExternalAuditRow))
    session.execute(delete(QcSwabTestRow))
    session.execute(delete(QcProductTestRow))
    session.execute(delete(QcDailyDefectRow))
    session.execute(delete(QcMaterialReceiptRow))
    session.execute(delete(QcSwabPointRow))


def _clear_hr(session: Session) -> None:
    session.execute(delete(HrAttendancePunchRow))
    session.execute(delete(HrLaborRateRow))
    session.execute(delete(HrEmployeeRow))


def _clear_inventory_delivery_master(session: Session) -> None:
    session.execute(delete(DeliveryProjectStepRow))
    session.execute(delete(DeliveryProjectRow))
    session.execute(delete(InvIssueRow))
    session.execute(delete(InvInboundDailyRow))
    session.execute(delete(HrGroupAttendanceRow))
    session.execute(delete(MdRawMaterialRow))
    session.execute(delete(MdSupplierRow))


def _drop_resync_markers(session: Session) -> None:
    for key in (
        DEMO_VERSION_KEY,
        HR_VERSION_KEY,
        LINES_VERSION_KEY,
        STATS_VERSION_KEY,
        SCENARIO_LOCK_KEY,
    ):
        row = session.get(AppSettingRow, key)
        if row is not None:
            session.delete(row)


def _count_snapshot(session: Session) -> dict[str, int]:
    return {
        "items": int(session.scalar(select(func.count()).select_from(MdItemRow)) or 0),
        "orders": int(session.scalar(select(func.count()).select_from(SoOrderRow)) or 0),
        "quotes": int(session.scalar(select(func.count()).select_from(CrmQuoteRow)) or 0),
        "customers": int(session.scalar(select(func.count()).select_from(CrmCustomerRow)) or 0),
        "employees": int(session.scalar(select(func.count()).select_from(HrEmployeeRow)) or 0),
    }


def clear_demo_business_data(session: Session, *, wipe_audit: bool = True) -> dict:
    """清空各模块业务数据，保留 demo_run 记录；维持手工数据模式。"""
    reset_order_scenario(session)
    _clear_crm_and_sales(session)
    _clear_qc_ledger(session)
    _clear_hr(session)
    _clear_inventory_delivery_master(session)
    if wipe_audit:
        session.execute(delete(AuditLogRow))
    _drop_resync_markers(session)
    clear_master_and_orders(session)
    set_scenario_lock(session, True)
    set_manual_data_mode(session, True)
    session.flush()
    return {"manual_data_mode": True, "counts": _count_snapshot(session)}


def reset_demo_system(session: Session) -> dict:
    """清空全部业务数据与全部演示线记录；系统回到干净状态。"""
    guided = _clear_guided_demo(session)
    business = clear_demo_business_data(session)
    return {"guided_demo": guided, **business}
