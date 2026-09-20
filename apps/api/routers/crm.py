"""M2 CRM + CTP + 固定报表。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.ctp_service import ctp_feasibility, ctp_from_template_order, ctp_order_feasibility
from db.contract_queries import (
    add_receipt,
    contract_detail,
    create_contract,
    customer_metrics,
    list_contracts,
)
from db.crm_queries import (
    customer_detail,
    funnel_report,
    list_customers,
    list_opportunities,
    list_samples,
    opportunity_detail,
    sample_weekly_report,
)
from db.quote_service import (
    approve_quote,
    create_quote,
    get_quote,
    list_quotes,
    submit_quote,
    update_quote,
    void_quote,
)
from db.sample_workflow import add_sample_step, close_sample, preview_next_round, sample_detail
from db.demo_crm_seed import ensure_demo_crm
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def _sales_filter(role: str) -> str | None:
    if role == "SALES":
        return "陈雨桐"
    return None


class CtpLineIn(BaseModel):
    item_code: str
    qty: int = Field(gt=0)
    unit: str = "BOX"


class CtpBody(BaseModel):
    item_code: str = "P2"
    qty_order: int = Field(default=200, gt=0)
    unit: str = "BOX"
    due_date: date
    template_order_no: str | None = None
    lines: list[CtpLineIn] | None = None


class PaymentPlanIn(BaseModel):
    line_no: int
    milestone: str = ""
    condition_type: str = "CUSTOM"
    condition_note: str = ""
    plan_date: date
    plan_amount: float = Field(gt=0)


class CreateContractBody(BaseModel):
    customer_code: str
    title: str
    contract_amount: float = Field(gt=0)
    status: str = "ACTIVE"
    signed_date: date | None = None
    opportunity_id: int | None = None
    terms: dict = Field(default_factory=dict)
    plans: list[PaymentPlanIn] = Field(default_factory=list)


class ReceiptBody(BaseModel):
    receipt_date: date
    amount: float = Field(gt=0)
    method: str = "银行转账"
    ref_no: str = ""
    note: str = ""
    plan_id: int | None = None


class SampleCloseBody(BaseModel):
    event_date: date | None = None
    evidence_text: str = ""
    evidence_images: list[str] = Field(default_factory=list)


class SampleStepBody(BaseModel):
    stage: str
    event_date: date
    product_desc: str = ""
    situation_desc: str = ""
    evidence_text: str = ""
    evidence_images: list[str] = Field(default_factory=list)
    is_final: bool = False
    is_rework: bool = False


class QuoteLineIn(BaseModel):
    item_code: str | None = None
    item_name: str = ""
    image_ref: str = ""
    spec: str = ""
    process_label: str = ""
    category: str = ""
    unit_price_tax_in: Decimal = Decimal("0")
    moq: Decimal | None = None
    qty: Decimal = Field(default=Decimal("1"))
    uom: str = "BOX"
    mold_fee: Decimal = Decimal("0")
    rebate_qty: Decimal | None = None
    rebate_uom: str | None = None
    note: str = ""


class QuoteCreateIn(BaseModel):
    customer_code: str
    lines: list[QuoteLineIn] = Field(min_length=1)
    sample_code: str | None = None
    owner_sales: str = ""
    opportunity_id: int | None = None
    tax_rate: Decimal = Decimal("0.13")
    valid_until: date | None = None
    note: str = ""


class QuoteUpdateIn(BaseModel):
    customer_code: str | None = None
    lines: list[QuoteLineIn] | None = None
    sample_code: str | None = None
    owner_sales: str | None = None
    opportunity_id: int | None = None
    tax_rate: Decimal | None = None
    valid_until: date | None = None
    note: str | None = None


def register_crm(app, get_db):
    @app.get("/api/crm/customers")
    def crm_customers(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        db.flush()
        return {
            "code": 0,
            "message": "",
            "data": list_customers(db, role=role, owner_filter=_sales_filter(role)),
        }

    @app.get("/api/crm/customers/metrics")
    def crm_customer_metrics(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": customer_metrics(db, owner_filter=_sales_filter(role)),
        }

    @app.get("/api/crm/customers/{code}")
    def crm_customer_one(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        from db.qc_seed import ensure_qc_seed

        ensure_qc_seed(db)
        data = customer_detail(db, code)
        if data is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/crm/contracts")
    def crm_contracts_list(
        customer_code: str | None = None,
        status: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": list_contracts(
                db,
                customer_code=customer_code,
                status=status,
                owner_filter=_sales_filter(role),
            ),
        }

    @app.get("/api/crm/contracts/{contract_no}")
    def crm_contract_one(
        contract_no: str,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        data = contract_detail(db, contract_no, today=today or date(2026, 9, 15))
        if data is None:
            raise HTTPException(status_code=404, detail="合同不存在")
        if role == "SALES" and _sales_filter(role):
            cust = data["customer_code"]
            from db.tables import CrmCustomerRow

            c = db.get(CrmCustomerRow, cust)
            if c and c.owner_sales != _sales_filter(role):
                raise HTTPException(status_code=403, detail="无权查看")
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/contracts")
    def crm_contract_create(
        body: CreateContractBody,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权新建合同")
        ensure_demo_crm(db)
        anchor = today or date(2026, 9, 15)
        try:
            data = create_contract(
                db,
                customer_code=body.customer_code,
                title=body.title,
                contract_amount=Decimal(str(body.contract_amount)),
                status=body.status,
                signed_date=body.signed_date,
                owner_sales="",
                terms=body.terms,
                plans=[p.model_dump() for p in body.plans],
                opportunity_id=body.opportunity_id,
                today=anchor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/contracts/{contract_no}/receipts")
    def crm_contract_receipt(
        contract_no: str,
        body: ReceiptBody,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "FIN", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权登记回款")
        ensure_demo_crm(db)
        anchor = today or date(2026, 9, 15)
        try:
            data = add_receipt(
                db,
                contract_no,
                receipt_date=body.receipt_date,
                amount=Decimal(str(body.amount)),
                method=body.method,
                ref_no=body.ref_no,
                note=body.note,
                plan_id=body.plan_id,
                today=anchor,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="合同不存在") from None
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/crm/opportunities/{opp_id}")
    def crm_opportunity_one(
        opp_id: int,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        data = opportunity_detail(db, opp_id)
        if data is None:
            raise HTTPException(status_code=404, detail="商机不存在")
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/crm/opportunities")
    def crm_opportunities(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": list_opportunities(db, role=role, owner_filter=_sales_filter(role)),
        }

    @app.get("/api/crm/samples/{code}")
    def crm_sample_one(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        data = sample_detail(db, code)
        if data is None:
            raise HTTPException(status_code=404, detail="样品不存在")
        if role == "SALES" and _sales_filter(role):
            owner = _sales_filter(role)
            if data["owner_sales"] != owner:
                raise HTTPException(status_code=403, detail="无权查看该样品")
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/crm/samples/{code}/steps/preview")
    def crm_sample_step_preview(
        code: str,
        stage: str = "打样",
        is_rework: bool = False,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            data = preview_next_round(db, code, stage=stage, is_rework=is_rework)
        except KeyError:
            raise HTTPException(status_code=404, detail="样品不存在") from None
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/samples/{code}/steps")
    def crm_sample_add_step(
        code: str,
        body: SampleStepBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES"):
            raise HTTPException(status_code=403, detail="无权维护打样记录")
        ensure_demo_crm(db)
        data = sample_detail(db, code)
        if data is None:
            raise HTTPException(status_code=404, detail="样品不存在")
        if role == "SALES" and _sales_filter(role) and data["owner_sales"] != _sales_filter(role):
            raise HTTPException(status_code=403, detail="无权维护该样品")
        try:
            updated = add_sample_step(
                db,
                code,
                stage=body.stage,
                event_date=body.event_date,
                product_desc=body.product_desc,
                situation_desc=body.situation_desc,
                evidence_text=body.evidence_text,
                evidence_images=body.evidence_images,
                is_final=body.is_final,
                is_rework=body.is_rework,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="样品不存在") from None
        db.commit()
        return {"code": 0, "message": "", "data": updated}

    @app.post("/api/crm/samples/{code}/close")
    def crm_sample_close(
        code: str,
        body: SampleCloseBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES"):
            raise HTTPException(status_code=403, detail="无权结案打样")
        ensure_demo_crm(db)
        data = sample_detail(db, code)
        if data is None:
            raise HTTPException(status_code=404, detail="样品不存在")
        if role == "SALES" and _sales_filter(role) and data["owner_sales"] != _sales_filter(role):
            raise HTTPException(status_code=403, detail="无权结案该样品")
        try:
            closed = close_sample(
                db,
                code,
                evidence_text=body.evidence_text,
                evidence_images=body.evidence_images,
                event_date=body.event_date,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="样品不存在") from None
        db.commit()
        return {"code": 0, "message": "", "data": closed}

    @app.get("/api/crm/samples")
    def crm_samples(
        active_only: bool = False,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": list_samples(
                db,
                role=role,
                owner_filter=_sales_filter(role),
                active_only=active_only,
            ),
        }

    def _quote_write_roles(role: str) -> None:
        if role not in ("GM", "SALES_MGR", "SALES"):
            raise HTTPException(status_code=403, detail="无权维护报价")

    def _quote_approve_roles(role: str) -> None:
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="仅销售总监/总经理可批准报价")

    @app.get("/api/crm/quotes")
    def crm_quotes(
        customer_code: str | None = None,
        status: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES", "FIN", "PMC"):
            raise HTTPException(status_code=403, detail="无权查看报价")
        ensure_demo_crm(db)
        hide = role == "WH"
        return {
            "code": 0,
            "message": "",
            "data": list_quotes(db, customer_code=customer_code, status=status, hide_amount=hide),
        }

    @app.post("/api/crm/quotes")
    def crm_quote_create(
        body: QuoteCreateIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _quote_write_roles(role)
        ensure_demo_crm(db)
        try:
            data = create_quote(
                db,
                customer_code=body.customer_code,
                lines=[ln.model_dump() for ln in body.lines],
                sample_code=body.sample_code,
                owner_sales=body.owner_sales,
                opportunity_id=body.opportunity_id,
                tax_rate=body.tax_rate,
                valid_until=body.valid_until,
                note=body.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "报价已创建", "data": data}

    @app.get("/api/crm/quotes/{code}")
    def crm_quote_detail(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES", "FIN", "PMC"):
            raise HTTPException(status_code=403, detail="无权查看报价")
        ensure_demo_crm(db)
        try:
            data = get_quote(db, code)
        except KeyError:
            raise HTTPException(status_code=404, detail="报价单不存在") from None
        if role == "WH":
            data["total_amount"] = None
        return {"code": 0, "message": "", "data": data}

    @app.put("/api/crm/quotes/{code}")
    def crm_quote_update(
        code: str,
        body: QuoteUpdateIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _quote_write_roles(role)
        ensure_demo_crm(db)
        payload = body.model_dump(exclude_unset=True)
        if "lines" in payload and payload["lines"] is not None:
            payload["lines"] = [ln if isinstance(ln, dict) else ln for ln in payload["lines"]]
        try:
            data = update_quote(db, code, **payload)
        except KeyError:
            raise HTTPException(status_code=404, detail="报价单不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "报价已更新", "data": data}

    @app.post("/api/crm/quotes/{code}/submit")
    def crm_quote_submit(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _quote_write_roles(role)
        ensure_demo_crm(db)
        try:
            data = submit_quote(db, code)
        except KeyError:
            raise HTTPException(status_code=404, detail="报价单不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "报价已提交", "data": data}

    @app.post("/api/crm/quotes/{code}/approve")
    def crm_quote_approve(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _quote_approve_roles(role)
        ensure_demo_crm(db)
        try:
            data = approve_quote(db, code)
        except KeyError:
            raise HTTPException(status_code=404, detail="报价单不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "报价已批准", "data": data}

    @app.post("/api/crm/quotes/{code}/void")
    def crm_quote_void(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权作废报价")
        ensure_demo_crm(db)
        try:
            data = void_quote(db, code)
        except KeyError:
            raise HTTPException(status_code=404, detail="报价单不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "报价已作废", "data": data}

    @app.get("/api/crm/reports/funnel")
    def crm_funnel(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        return {"code": 0, "message": "", "data": funnel_report(db)}

    @app.get("/api/crm/reports/sample-weekly")
    def crm_sample_weekly(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        return {"code": 0, "message": "", "data": sample_weekly_report(db)}

    @app.post("/api/crm/ctp")
    def crm_ctp(
        body: CtpBody,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        anchor = today or date(2026, 9, 15)
        try:
            if body.lines:
                data = ctp_order_feasibility(
                    db,
                    lines=[ln.model_dump() for ln in body.lines],
                    due_date=body.due_date,
                    today=anchor,
                )
            elif body.template_order_no:
                data = ctp_from_template_order(
                    db,
                    template_order_no=body.template_order_no,
                    new_due=body.due_date,
                    today=anchor,
                )
            else:
                data = ctp_feasibility(
                    db,
                    item_code=body.item_code,
                    qty_order=Decimal(str(body.qty_order)),
                    unit=body.unit,
                    due_date=body.due_date,
                    today=anchor,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "", "data": data}
