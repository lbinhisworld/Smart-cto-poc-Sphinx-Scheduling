"""来料台账与异常闭环（BR-QC-01 / BR-QC-02）。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.master_data_kingdee import get_raw_material, get_supplier
from db.qc_period import month_key
from db.tables import QcExceptionEventRow, QcMaterialExceptionRow, QcMaterialReceiptRow

_EXCEPTION_TRANSITIONS: dict[str, dict[str, str]] = {
    "OPEN": {"start": "IN_PROGRESS", "close": "CLOSED"},
    "IN_PROGRESS": {"submit_verify": "PENDING_VERIFY", "close": "CLOSED"},
    "PENDING_VERIFY": {"close": "CLOSED", "reject": "IN_PROGRESS"},
}


def _validate_master(session: Session, *, supplier_code: str, material_code: str) -> tuple[str, str, str, str]:
    sup = get_supplier(session, supplier_code)
    if sup is None or sup.status != "ACTIVE":
        raise ValueError(f"供应商编码不存在或未启用: {supplier_code}（BR-QC-02）")
    mat = get_raw_material(session, material_code)
    if mat is None or not mat.is_active:
        raise ValueError(f"原辅料编码不存在或未启用: {material_code}（BR-QC-02）")
    return sup.name, mat.name, mat.spec, mat.default_uom


def _next_no(session: Session, prefix: str, col) -> str:
    count = session.scalar(select(func.count()).select_from(col)) or 0
    return f"{prefix}-{count + 1:05d}"


def receipt_to_dict(r: QcMaterialReceiptRow) -> dict:
    return {
        "id": r.id,
        "receipt_no": r.receipt_no,
        "incoming_date": r.incoming_date.isoformat(),
        "month_key": r.month_key,
        "material_code": r.material_code,
        "material_name": r.material_name,
        "spec": r.spec,
        "attr": r.attr,
        "batch_no": r.batch_no,
        "shelf_life_until": r.shelf_life_until.isoformat() if r.shelf_life_until else None,
        "shelf_life_text": r.shelf_life_text,
        "supplier_code": r.supplier_code,
        "supplier_name": r.supplier_name,
        "qty": str(r.qty),
        "uom": r.uom,
        "remark": r.remark,
        "kingdee_doc_no": r.kingdee_doc_no,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "created_by": r.created_by,
    }


def list_receipts(
    session: Session,
    *,
    month: str | None = None,
    supplier_code: str | None = None,
    material_code: str | None = None,
    batch_no: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = select(QcMaterialReceiptRow).order_by(QcMaterialReceiptRow.incoming_date.desc(), QcMaterialReceiptRow.id.desc())
    if month:
        stmt = stmt.where(QcMaterialReceiptRow.month_key == month)
    if supplier_code:
        stmt = stmt.where(QcMaterialReceiptRow.supplier_code == supplier_code)
    if material_code:
        stmt = stmt.where(QcMaterialReceiptRow.material_code == material_code)
    if batch_no:
        stmt = stmt.where(QcMaterialReceiptRow.batch_no.contains(batch_no))
    rows = session.scalars(stmt.limit(limit)).all()
    return [receipt_to_dict(r) for r in rows]


def create_receipt(session: Session, body: dict, *, actor: str) -> dict:
    supplier_code = body["supplier_code"]
    material_code = body["material_code"]
    sup_name, mat_name, spec, default_uom = _validate_master(
        session, supplier_code=supplier_code, material_code=material_code
    )
    incoming = date.fromisoformat(body["incoming_date"])
    now = datetime.now(UTC)
    row = QcMaterialReceiptRow(
        receipt_no=body.get("receipt_no") or _next_no(session, "RCV", QcMaterialReceiptRow),
        incoming_date=incoming,
        month_key=month_key(incoming),
        material_code=material_code,
        material_name=mat_name,
        spec=body.get("spec") or spec,
        attr=body.get("attr") or "",
        batch_no=body.get("batch_no") or "",
        shelf_life_until=date.fromisoformat(body["shelf_life_until"]) if body.get("shelf_life_until") else None,
        shelf_life_text=body.get("shelf_life_text") or "",
        supplier_code=supplier_code,
        supplier_name=sup_name,
        qty=Decimal(str(body["qty"])),
        uom=body.get("uom") or default_uom,
        remark=body.get("remark") or "",
        kingdee_doc_no=body.get("kingdee_doc_no") or "",
        created_at=now,
        created_by=actor,
    )
    session.add(row)
    session.flush()
    return receipt_to_dict(row)


def exception_to_dict(e: QcMaterialExceptionRow, receipt: QcMaterialReceiptRow | None = None) -> dict:
    d = {
        "id": e.id,
        "exception_no": e.exception_no,
        "receipt_id": e.receipt_id,
        "discovered_at": e.discovered_at.isoformat(),
        "month_key": e.month_key,
        "phenomenon": e.phenomenon,
        "status": e.status,
        "handler": e.handler,
        "handler_dept": e.handler_dept,
        "disposition": e.disposition,
        "disposition_detail": e.disposition_detail,
        "closed_at": e.closed_at.isoformat() if e.closed_at else None,
        "closed_by": e.closed_by,
        "close_result": e.close_result,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "created_by": e.created_by,
    }
    if receipt is not None:
        d["receipt"] = receipt_to_dict(receipt)
    return d


def list_exceptions(
    session: Session,
    *,
    month: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    stmt = select(QcMaterialExceptionRow).order_by(
        QcMaterialExceptionRow.discovered_at.desc(), QcMaterialExceptionRow.id.desc()
    )
    if month:
        stmt = stmt.where(QcMaterialExceptionRow.month_key == month)
    if status:
        stmt = stmt.where(QcMaterialExceptionRow.status == status)
    rows = session.scalars(stmt.limit(limit)).all()
    out: list[dict] = []
    for e in rows:
        rcpt = session.get(QcMaterialReceiptRow, e.receipt_id)
        out.append(exception_to_dict(e, rcpt))
    return out


def create_exception(session: Session, body: dict, *, actor: str) -> dict:
    receipt_id = int(body["receipt_id"])
    receipt = session.get(QcMaterialReceiptRow, receipt_id)
    if receipt is None:
        raise ValueError("来料单不存在")
    discovered = date.fromisoformat(body.get("discovered_at") or receipt.incoming_date.isoformat())
    now = datetime.now(UTC)
    row = QcMaterialExceptionRow(
        exception_no=body.get("exception_no") or _next_no(session, "EXC", QcMaterialExceptionRow),
        receipt_id=receipt_id,
        discovered_at=discovered,
        month_key=month_key(discovered),
        phenomenon=body["phenomenon"],
        status="OPEN",
        handler=body.get("handler") or "",
        handler_dept=body.get("handler_dept") or "",
        disposition=body.get("disposition") or "",
        disposition_detail=body.get("disposition_detail") or "",
        created_at=now,
        created_by=actor,
    )
    session.add(row)
    session.flush()
    session.add(
        QcExceptionEventRow(
            exception_id=row.id,
            from_status="",
            to_status="OPEN",
            action="create",
            actor=actor,
            note="",
            created_at=now,
        )
    )
    return exception_to_dict(row, receipt)


def transition_exception(
    session: Session,
    exception_id: int,
    *,
    action: str,
    actor: str,
    note: str = "",
    disposition: str | None = None,
    disposition_detail: str | None = None,
    close_result: str | None = None,
    force: bool = False,
) -> dict:
    row = session.get(QcMaterialExceptionRow, exception_id)
    if row is None:
        raise ValueError("异常单不存在")
    if force and action == "close":
        new_status = "CLOSED"
    else:
        mapping = _EXCEPTION_TRANSITIONS.get(row.status, {})
        new_status = mapping.get(action)
        if not new_status:
            raise ValueError(f"非法状态流转: {row.status} + {action}")
    now = datetime.now(UTC)
    old = row.status
    row.status = new_status
    if disposition is not None:
        row.disposition = disposition
    if disposition_detail is not None:
        row.disposition_detail = disposition_detail
    if new_status == "CLOSED":
        row.closed_at = now
        row.closed_by = actor
        row.close_result = close_result or row.close_result or "已关闭"
    session.add(
        QcExceptionEventRow(
            exception_id=row.id,
            from_status=old,
            to_status=new_status,
            action=action,
            actor=actor,
            note=note,
            created_at=now,
        )
    )
    receipt = session.get(QcMaterialReceiptRow, row.receipt_id)
    return exception_to_dict(row, receipt)


def list_open_exceptions_past_sla(session: Session, *, today: date, sla_days: int) -> list[dict]:
    cutoff = today.toordinal() - sla_days
    rows = session.scalars(
        select(QcMaterialExceptionRow).where(
            QcMaterialExceptionRow.status.in_(("OPEN", "IN_PROGRESS", "PENDING_VERIFY"))
        )
    ).all()
    out: list[dict] = []
    for e in rows:
        if e.discovered_at.toordinal() <= cutoff:
            rcpt = session.get(QcMaterialReceiptRow, e.receipt_id)
            out.append(exception_to_dict(e, rcpt))
    return out
