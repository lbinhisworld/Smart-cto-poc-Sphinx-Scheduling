"""M9 品控台账 API。"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.master_data_kingdee import list_raw_materials, list_suppliers
from db.qc_attachment import add_attachments, delete_attachment, list_attachments
from db.qc_export import export_exceptions_csv, export_receipts_csv
from db.qc_ledgers import (
    create_audit,
    create_complaint,
    create_daily_defect,
    create_lab_external,
    create_product_test,
    create_swab_test,
    list_audits,
    list_complaints,
    list_daily_defects,
    list_lab_external,
    list_product_tests,
    list_swab_points,
    list_swab_tests,
)
from db.qc_material import create_exception, create_receipt, list_exceptions, list_receipts, transition_exception
from db.qc_metrics import qc_summary
from db.qc_seed import ensure_qc_seed
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def _actor(role: str) -> str:
    u = user_for_role(role)
    return u.name if u else role


def _require_qc_write(role: str) -> None:
    if role not in ("GM", "QC", "WH"):
        raise HTTPException(status_code=403, detail="无品控写权限")


class ReceiptIn(BaseModel):
    incoming_date: date
    supplier_code: str
    material_code: str
    qty: float = Field(gt=0)
    uom: str | None = None
    attr: str = ""
    batch_no: str = ""
    shelf_life_until: date | None = None
    shelf_life_text: str = ""
    spec: str = ""
    remark: str = ""
    kingdee_doc_no: str = ""


class ExceptionIn(BaseModel):
    receipt_id: int
    phenomenon: str
    discovered_at: date | None = None
    handler: str = ""
    handler_dept: str = ""


class TransitionIn(BaseModel):
    action: str
    note: str = ""
    disposition: str | None = None
    disposition_detail: str | None = None
    close_result: str | None = None
    force: bool = False


class AttachmentIn(BaseModel):
    entity_type: str
    entity_id: int
    items: list[dict] = Field(default_factory=list)


def register_qc(app, get_db):
    @app.get("/api/qc/summary")
    def qc_sum(
        today: date | None = Query(default=None),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        anchor = today or date(2026, 9, 15)
        return {"code": 0, "message": "", "data": qc_summary(db, today=anchor)}

    @app.get("/api/qc/master/suppliers")
    def qc_suppliers(
        q: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_suppliers(db, q=q)}

    @app.get("/api/qc/master/raw-materials")
    def qc_materials(
        q: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_raw_materials(db, q=q)}

    @app.get("/api/qc/receipts")
    def get_receipts(
        month: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_receipts(db, month=month)}

    @app.post("/api/qc/receipts")
    def post_receipt(
        body: ReceiptIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        ensure_qc_seed(db)
        try:
            data = create_receipt(db, body.model_dump(mode="json"), actor=_actor(role))
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/qc/exceptions")
    def get_exceptions(
        month: str | None = None,
        status: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_exceptions(db, month=month, status=status)}

    @app.post("/api/qc/exceptions")
    def post_exception(
        body: ExceptionIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        ensure_qc_seed(db)
        try:
            data = create_exception(db, body.model_dump(mode="json"), actor=_actor(role))
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/qc/exceptions/{exception_id}/transition")
    def post_transition(
        exception_id: int,
        body: TransitionIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "QC") and not (role == "WH" and body.action == "close" and body.force):
            if role not in ("GM", "QC"):
                raise HTTPException(status_code=403, detail="无异常流转权限")
        ensure_qc_seed(db)
        force = body.force and role == "GM"
        try:
            data = transition_exception(
                db,
                exception_id,
                action=body.action,
                actor=_actor(role),
                note=body.note,
                disposition=body.disposition,
                disposition_detail=body.disposition_detail,
                close_result=body.close_result,
                force=force,
            )
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/qc/daily-defects")
    def get_daily(
        month: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_daily_defects(db, month=month)}

    @app.post("/api/qc/daily-defects")
    def post_daily(
        body: dict,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        ensure_qc_seed(db)
        data = create_daily_defect(db, body, actor=_actor(role))
        db.commit()
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/qc/complaints")
    def get_complaints(
        month: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_complaints(db, month=month)}

    @app.post("/api/qc/complaints")
    def post_complaint(
        body: dict,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "QC", "SALES", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无客诉写权限")
        ensure_qc_seed(db)
        try:
            data = create_complaint(db, body, actor=_actor(role))
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/qc/audits")
    def get_audits(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_audits(db)}

    @app.post("/api/qc/audits")
    def post_audit(
        body: dict,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        ensure_qc_seed(db)
        try:
            data = create_audit(db, body, actor=_actor(role))
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/qc/lab-external")
    def get_lab_ext(
        month: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_lab_external(db, month=month)}

    @app.post("/api/qc/lab-external")
    def post_lab_ext(
        body: dict,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        ensure_qc_seed(db)
        data = create_lab_external(db, body, actor=_actor(role))
        db.commit()
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/qc/swab-points")
    def get_swab_points(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_swab_points(db)}

    @app.get("/api/qc/swab-tests")
    def get_swab_tests(
        month: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_swab_tests(db, month=month)}

    @app.post("/api/qc/swab-tests")
    def post_swab_test(
        body: dict,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        ensure_qc_seed(db)
        try:
            data = create_swab_test(db, body, actor=_actor(role))
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/qc/product-tests")
    def get_product_tests(
        month: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        return {"code": 0, "message": "", "data": list_product_tests(db, month=month)}

    @app.post("/api/qc/product-tests")
    def post_product_test(
        body: dict,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        ensure_qc_seed(db)
        try:
            data = create_product_test(db, body, actor=_actor(role))
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/qc/attachments")
    def get_attachments(
        entity_type: str,
        entity_id: int,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {
            "code": 0,
            "message": "",
            "data": list_attachments(db, entity_type=entity_type, entity_id=entity_id),
        }

    @app.post("/api/qc/attachments")
    def post_attachments(
        body: AttachmentIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        data = add_attachments(
            db,
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            items=body.items,
            uploaded_by=_actor(role),
        )
        db.commit()
        return {"code": 0, "message": "", "data": data}

    @app.delete("/api/qc/attachments/{attachment_id}")
    def del_attachment(
        attachment_id: int,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_qc_write(role)
        if not delete_attachment(db, attachment_id):
            raise HTTPException(status_code=404, detail="附件不存在")
        db.commit()
        return {"code": 0, "message": "", "data": {"deleted": True}}

    @app.get("/api/qc/export/{ledger}")
    def export_ledger(
        ledger: str,
        month: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_qc_seed(db)
        if ledger == "receipts":
            content = export_receipts_csv(db, month=month)
            name = "qc_receipts.csv"
        elif ledger == "exceptions":
            content = export_exceptions_csv(db, month=month)
            name = "qc_exceptions.csv"
        else:
            raise HTTPException(status_code=404, detail="未知台账")
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )
