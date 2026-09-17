"""M9 其余台账 CRUD。"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.qc_period import month_key, period_fields
from db.qc_verdict import compute_product_verdict, compute_swab_verdict, validate_override
from db.tables import (
    CrmCustomerRow,
    MdItemRow,
    QcCustomerComplaintRow,
    QcDailyDefectRow,
    QcExternalAuditRow,
    QcLabExternalRequestRow,
    QcProductTestRow,
    QcSwabPointRow,
    QcSwabTestRow,
)


def _now() -> datetime:
    return datetime.now(UTC)


def create_daily_defect(session: Session, body: dict, *, actor: str) -> dict:
    rd = date.fromisoformat(body["record_date"])
    pf = period_fields(rd)
    row = QcDailyDefectRow(
        month_key=pf["month_key"],
        record_date=rd,
        week_no=pf["week_no"],
        dept_found=body["dept_found"],
        shift=body.get("shift") or "",
        item_code=body.get("item_code"),
        model_no=body.get("model_no") or "",
        product_name=body["product_name"],
        production_date=date.fromisoformat(body["production_date"]) if body.get("production_date") else None,
        defect_qty=int(body.get("defect_qty") or 0),
        defect_category=body.get("defect_category") or "",
        defect_specific=body.get("defect_specific") or "",
        defect_detail=body.get("defect_detail") or "",
        handling_result=body.get("handling_result") or "",
        dept_responsible=body.get("dept_responsible") or "",
        case_no=body.get("case_no") or "",
        created_at=_now(),
        created_by=actor,
    )
    session.add(row)
    session.flush()
    return _daily_dict(row)


def list_daily_defects(session: Session, *, month: str | None = None, limit: int = 200) -> list[dict]:
    stmt = select(QcDailyDefectRow).order_by(QcDailyDefectRow.record_date.desc())
    if month:
        stmt = stmt.where(QcDailyDefectRow.month_key == month)
    return [_daily_dict(r) for r in session.scalars(stmt.limit(limit)).all()]


def _daily_dict(r: QcDailyDefectRow) -> dict:
    return {
        "id": r.id,
        "month_key": r.month_key,
        "record_date": r.record_date.isoformat(),
        "week_no": r.week_no,
        "dept_found": r.dept_found,
        "shift": r.shift,
        "item_code": r.item_code,
        "model_no": r.model_no,
        "product_name": r.product_name,
        "production_date": r.production_date.isoformat() if r.production_date else None,
        "defect_qty": r.defect_qty,
        "defect_category": r.defect_category,
        "defect_specific": r.defect_specific,
        "defect_detail": r.defect_detail,
        "handling_result": r.handling_result,
        "dept_responsible": r.dept_responsible,
        "case_no": r.case_no,
    }


def create_complaint(session: Session, body: dict, *, actor: str) -> dict:
    item_code = body["item_code"]
    if session.get(MdItemRow, item_code) is None:
        raise ValueError(f"产品编码不存在: {item_code}")
    rd = date.fromisoformat(body["record_date"])
    row = QcCustomerComplaintRow(
        month_key=month_key(rd),
        record_date=rd,
        customer_code=body.get("customer_code"),
        customer_name=body["customer_name"],
        customer_project=body.get("customer_project") or "",
        item_code=item_code,
        product_name=body.get("product_name") or "",
        production_date=date.fromisoformat(body["production_date"]) if body.get("production_date") else None,
        content=body["content"],
        category=body.get("category") or "",
        category_detail=body.get("category_detail") or "",
        sample_sent_date=date.fromisoformat(body["sample_sent_date"]) if body.get("sample_sent_date") else None,
        sample_result=body.get("sample_result") or "",
        root_cause=body.get("root_cause") or "",
        corrective_action=body.get("corrective_action") or "",
        status=body.get("status") or "OPEN",
        created_at=_now(),
        created_by=actor,
    )
    session.add(row)
    session.flush()
    return _complaint_dict(row)


def list_complaints(session: Session, *, month: str | None = None, limit: int = 200) -> list[dict]:
    stmt = select(QcCustomerComplaintRow).order_by(QcCustomerComplaintRow.record_date.desc())
    if month:
        stmt = stmt.where(QcCustomerComplaintRow.month_key == month)
    return [_complaint_dict(r) for r in session.scalars(stmt.limit(limit)).all()]


def list_complaints_for_customer(session: Session, customer_code: str, *, limit: int = 20) -> list[dict]:
    """客户 360 子表：按 customer_code 关联，并兼容仅填客户名的历史行。"""
    cust = session.get(CrmCustomerRow, customer_code)
    name = cust.name if cust else ""
    rows = session.scalars(
        select(QcCustomerComplaintRow)
        .where(
            (QcCustomerComplaintRow.customer_code == customer_code)
            | (
                (QcCustomerComplaintRow.customer_code.is_(None))
                & (QcCustomerComplaintRow.customer_name == name)
                & (name != "")
            )
        )
        .order_by(QcCustomerComplaintRow.record_date.desc())
        .limit(limit)
    ).all()
    return [_complaint_dict(r) for r in rows]


def _complaint_dict(r: QcCustomerComplaintRow) -> dict:
    return {
        "id": r.id,
        "month_key": r.month_key,
        "record_date": r.record_date.isoformat(),
        "customer_code": r.customer_code,
        "customer_name": r.customer_name,
        "customer_project": r.customer_project,
        "item_code": r.item_code,
        "product_name": r.product_name,
        "production_date": r.production_date.isoformat() if r.production_date else None,
        "content": r.content,
        "category": r.category,
        "category_detail": r.category_detail,
        "sample_sent_date": r.sample_sent_date.isoformat() if r.sample_sent_date else None,
        "sample_result": r.sample_result,
        "root_cause": r.root_cause,
        "corrective_action": r.corrective_action,
        "status": r.status,
    }


def list_complaints_need_action(session: Session, *, today: date, sla_days: int) -> list[dict]:
    cutoff = today.toordinal() - sla_days
    rows = session.scalars(
        select(QcCustomerComplaintRow).where(
            QcCustomerComplaintRow.status != "CLOSED",
            QcCustomerComplaintRow.corrective_action == "",
        )
    ).all()
    return [_complaint_dict(r) for r in rows if r.record_date.toordinal() <= cutoff]


def create_audit(session: Session, body: dict, *, actor: str) -> dict:
    ad = date.fromisoformat(body["audit_date"])
    rr = date.fromisoformat(body["rectify_reply_date"]) if body.get("rectify_reply_date") else None
    if rr is not None and rr < ad:
        raise ValueError("整改回复时间不能早于审核日期")
    row = QcExternalAuditRow(
        audit_date=ad,
        category=body["category"],
        audit_type=body["audit_type"],
        nc_count=int(body.get("nc_count") or 0),
        audit_result=body["audit_result"],
        auditors=body["auditors"],
        rectify_reply_date=rr,
        remark=body.get("remark") or "",
        created_at=_now(),
        created_by=actor,
    )
    session.add(row)
    session.flush()
    return _audit_dict(row)


def list_audits(session: Session, limit: int = 200) -> list[dict]:
    rows = session.scalars(
        select(QcExternalAuditRow).order_by(QcExternalAuditRow.audit_date.desc()).limit(limit)
    ).all()
    return [_audit_dict(r) for r in rows]


def _audit_dict(r: QcExternalAuditRow) -> dict:
    return {
        "id": r.id,
        "audit_date": r.audit_date.isoformat(),
        "category": r.category,
        "audit_type": r.audit_type,
        "nc_count": r.nc_count,
        "audit_result": r.audit_result,
        "auditors": r.auditors,
        "rectify_reply_date": r.rectify_reply_date.isoformat() if r.rectify_reply_date else None,
        "remark": r.remark,
    }


def create_lab_external(session: Session, body: dict, *, actor: str) -> dict:
    ad = date.fromisoformat(body["accepted_date"])
    row = QcLabExternalRequestRow(
        month_key=month_key(ad),
        accepted_date=ad,
        customer_code=body.get("customer_code"),
        customer_name=body["customer_name"],
        product_name=body["product_name"],
        test_purpose=body.get("test_purpose") or "",
        test_items=body.get("test_items") or "",
        request_dept=body.get("request_dept") or "",
        report_date=date.fromisoformat(body["report_date"]) if body.get("report_date") else None,
        remark=body.get("remark") or "",
        created_at=_now(),
        created_by=actor,
    )
    session.add(row)
    session.flush()
    return _lab_ext_dict(row)


def list_lab_external(session: Session, *, month: str | None = None, limit: int = 200) -> list[dict]:
    stmt = select(QcLabExternalRequestRow).order_by(QcLabExternalRequestRow.accepted_date.desc())
    if month:
        stmt = stmt.where(QcLabExternalRequestRow.month_key == month)
    return [_lab_ext_dict(r) for r in session.scalars(stmt.limit(limit)).all()]


def _lab_ext_dict(r: QcLabExternalRequestRow) -> dict:
    return {
        "id": r.id,
        "month_key": r.month_key,
        "accepted_date": r.accepted_date.isoformat(),
        "customer_code": r.customer_code,
        "customer_name": r.customer_name,
        "product_name": r.product_name,
        "test_purpose": r.test_purpose,
        "test_items": r.test_items,
        "request_dept": r.request_dept,
        "report_date": r.report_date.isoformat() if r.report_date else None,
        "remark": r.remark,
    }


def list_swab_points(session: Session) -> list[dict]:
    rows = session.scalars(
        select(QcSwabPointRow).where(QcSwabPointRow.is_active.is_(True)).order_by(QcSwabPointRow.point_code)
    ).all()
    return [
        {
            "id": r.id,
            "point_code": r.point_code,
            "point_name": r.point_name,
            "detail_name": r.detail_name,
        }
        for r in rows
    ]


def create_swab_test(session: Session, body: dict, *, actor: str) -> dict:
    exp = date.fromisoformat(body["experiment_date"])
    samp = date.fromisoformat(body["sampling_date"])
    pf = period_fields(samp)
    tpc_raw = body.get("tpc_cfu_ml") or ""
    col_raw = body.get("coliform_cfu_ml") or ""
    computed, fail_draft = compute_swab_verdict(tpc_cfu_ml=tpc_raw, coliform_cfu_ml=col_raw)
    final = body.get("verdict_final")
    override = body.get("override_reason") or ""
    validate_override(computed=computed, final=final, override_reason=override)
    row = QcSwabTestRow(
        point_id=int(body["point_id"]),
        month_key=pf["month_key"],
        experiment_date=exp,
        weekday=pf["weekday"],
        week_no=pf["week_no"],
        sampling_date=samp,
        tpc_cfu_ml=tpc_raw,
        tpc_cfu_ml_raw=tpc_raw,
        coliform_cfu_ml=col_raw,
        coliform_cfu_ml_raw=col_raw,
        verdict_computed=computed,
        verdict_final=final,
        override_reason=override,
        fail_reason=body.get("fail_reason") or fail_draft,
        created_at=_now(),
        created_by=actor,
    )
    session.add(row)
    session.flush()
    return _swab_dict(row)


def list_swab_tests(session: Session, *, month: str | None = None, limit: int = 200) -> list[dict]:
    stmt = select(QcSwabTestRow).order_by(QcSwabTestRow.sampling_date.desc())
    if month:
        stmt = stmt.where(QcSwabTestRow.month_key == month)
    return [_swab_dict(r) for r in session.scalars(stmt.limit(limit)).all()]


def _swab_dict(r: QcSwabTestRow) -> dict:
    return {
        "id": r.id,
        "point_id": r.point_id,
        "month_key": r.month_key,
        "experiment_date": r.experiment_date.isoformat(),
        "weekday": r.weekday,
        "week_no": r.week_no,
        "sampling_date": r.sampling_date.isoformat(),
        "tpc_cfu_ml": r.tpc_cfu_ml,
        "coliform_cfu_ml": r.coliform_cfu_ml,
        "verdict_computed": r.verdict_computed,
        "verdict_final": r.verdict_final,
        "verdict_effective": r.verdict_final or r.verdict_computed,
        "override_reason": r.override_reason,
        "fail_reason": r.fail_reason,
    }


def create_product_test(session: Session, body: dict, *, actor: str) -> dict:
    exp = date.fromisoformat(body["experiment_date"])
    samp = date.fromisoformat(body["sampling_date"])
    pf = period_fields(samp)
    moisture = body.get("moisture_pct") or ""
    col = body.get("coliform_cfu_g") or ""
    tpc = body.get("tpc_cfu_g") or ""
    computed, fail_draft = compute_product_verdict(
        moisture_pct=moisture, coliform_cfu_g=col, tpc_cfu_g=tpc
    )
    final = body.get("verdict_final")
    override = body.get("override_reason") or ""
    validate_override(computed=computed, final=final, override_reason=override)
    row = QcProductTestRow(
        month_key=pf["month_key"],
        experiment_date=exp,
        weekday=pf["weekday"],
        week_no=pf["week_no"],
        customer_code=body.get("customer_code"),
        customer_name=body.get("customer_name") or "",
        product_name=body["product_name"],
        item_code=body.get("item_code"),
        sampling_date=samp,
        moisture_pct=moisture,
        moisture_pct_raw=moisture,
        coliform_cfu_g=col,
        coliform_cfu_g_raw=col,
        tpc_cfu_g=tpc,
        tpc_cfu_g_raw=tpc,
        verdict_computed=computed,
        verdict_final=final,
        override_reason=override,
        fail_reason=body.get("fail_reason") or fail_draft,
        remark=body.get("remark") or "",
        created_at=_now(),
        created_by=actor,
    )
    session.add(row)
    session.flush()
    return _product_dict(row)


def list_product_tests(session: Session, *, month: str | None = None, limit: int = 200) -> list[dict]:
    stmt = select(QcProductTestRow).order_by(QcProductTestRow.sampling_date.desc())
    if month:
        stmt = stmt.where(QcProductTestRow.month_key == month)
    return [_product_dict(r) for r in session.scalars(stmt.limit(limit)).all()]


def _product_dict(r: QcProductTestRow) -> dict:
    return {
        "id": r.id,
        "month_key": r.month_key,
        "experiment_date": r.experiment_date.isoformat(),
        "weekday": r.weekday,
        "week_no": r.week_no,
        "customer_code": r.customer_code,
        "customer_name": r.customer_name,
        "product_name": r.product_name,
        "item_code": r.item_code,
        "sampling_date": r.sampling_date.isoformat(),
        "moisture_pct": r.moisture_pct,
        "coliform_cfu_g": r.coliform_cfu_g,
        "tpc_cfu_g": r.tpc_cfu_g,
        "verdict_computed": r.verdict_computed,
        "verdict_final": r.verdict_final,
        "verdict_effective": r.verdict_final or r.verdict_computed,
        "override_reason": r.override_reason,
        "fail_reason": r.fail_reason,
        "remark": r.remark,
    }
