"""M2 CRM + CTP + 固定报表。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.contracted_progress import list_contracted_progress
from db.crm_leads import (
    add_lead_follow,
    assign_leads,
    convert_lead_to_customer,
    convert_lead_to_opportunity,
    create_lead,
    get_lead,
    list_leads,
    list_pool_rules,
    lose_lead,
    save_pool_rule,
)
from db.crm_lead_report import lead_report, leads_for_drill
from db.crm_payment_ui import list_payment_plan_menu
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
    sample_weekly_report,
)
from db.quote_service import (
    approve_quote,
    create_quote,
    get_quote,
    list_quotes,
    submit_quote,
    update_quote,
    mark_requote,
    void_quote,
)
from db.sample_workflow import (
    add_sample_step,
    close_sample,
    confirm_sample_customer,
    preview_next_round,
    sample_detail,
)
from db.crm_sales import (
    board as sales_board,
    build_draft,
    confirm_visit,
    mobile_customer,
    mobile_customers,
    mobile_orders,
    ensure_sales_pack,
    grade_opportunity,
    home_for,
    llm_public_config,
    lose_opportunity,
    present_opportunity,
    save_llm_config,
    set_customer_quote,
    set_planned_labor,
    set_sample_cost,
)
from db.crm_goal_period import (
    delete_year_goal,
    ensure_demo_goal_period,
    list_goal_owner_candidates,
    list_goal_tree,
    reapply_demo_week_bump,
    save_period_targets,
    save_year_and_split,
    split_month_to_weeks,
    split_year_to_months,
    year_key,
)
from db.crm_customer_portal import (
    assign_sea,
    claim_sea,
    close_customer,
    ensure_demo_customer_portal,
    list_mine,
    list_sea,
    set_collaborators,
)
from db.crm_field_visit import (
    add_field_visit_log,
    check_in,
    check_out,
    confirm_field_visit_follow,
    create_field_visit,
    ensure_demo_field_visits,
    finalize_field_visit,
    get_field_visit,
    list_field_visit_stats,
    list_field_visits,
    match_customers_and_leads,
    parse_situation_note,
    timeline_text,
    update_field_visit,
)
from db.crm_follows import add_follow, ensure_demo_follows, list_follows
from db.crm_opportunity_ui import create_opportunity_for_customer
from db.crm_order_360 import order_360
from db.crm_quotes_ui import filter_quotes_by_tab, quote_tab_counts
from db.quote_pdf import quote_pdf_bytes, quote_print_html
from db.demo_crm_seed import ensure_demo_crm
from shared.auth import resolve_demo_actor, user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def _actor(role: str, x_demo_user: str | None) -> str:
    return resolve_demo_actor(role, x_demo_user)


def _sales_filter(role: str, x_demo_user: str | None = None) -> str | None:
    if role == "SALES":
        return _actor(role, x_demo_user) or None
    if role == "SALES_ASSIST":
        return "李业务"
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


class SampleConfirmBody(BaseModel):
    passed: bool
    fail_reason: str = ""
    ship_date: date | None = None


class SampleLaunchBody(BaseModel):
    opportunity_id: int
    due_date: date
    item_draft_name: str = ""
    start_date: date | None = None
    submit: bool = True


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


class VisitConfirmIn(BaseModel):
    customer_name: str = ""
    customer_code: str | None = None
    create_customer: bool = False
    visit_kind: str = "现有客户"
    narrative: str = ""
    outcome: str = "关系建联"
    next_step: str = ""
    next_date: date | None = None
    opportunity_name: str | None = None
    check_in_at: datetime
    check_out_at: datetime
    location_note: str = ""
    photo_note: str = ""


class VisitDraftIn(BaseModel):
    text: str
    today: date | None = None


class GradeIn(BaseModel):
    grade: str


class LoseIn(BaseModel):
    reason: str


class SampleCostIn(BaseModel):
    qty: int = Field(ge=0)
    material: Decimal
    labor_overhead: Decimal


class MoneyIn(BaseModel):
    amount: Decimal


class LlmConfigIn(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: str = ""


class QuoteUpdateIn(BaseModel):
    customer_code: str | None = None
    lines: list[QuoteLineIn] | None = None
    sample_code: str | None = None
    owner_sales: str | None = None
    opportunity_id: int | None = None
    tax_rate: Decimal | None = None
    valid_until: date | None = None
    note: str | None = None


class LeadBody(BaseModel):
    contact_name: str
    phone: str = ""
    gender: str = ""
    wechat: str = ""
    company_name: str = ""
    detail_text: str = ""
    industry: str = ""
    source: str = ""


class LeadAssignBody(BaseModel):
    codes: list[str]
    owner_sales: str


class LeadFollowBody(BaseModel):
    content: str
    next_follow_date: date | None = None


class PoolRuleBody(BaseModel):
    pool_name: str
    admin_name: str
    members: list[str] = Field(default_factory=list)
    recycle_days: int | None = None


class GoalPeriodSaveIn(BaseModel):
    owner_sales: str
    owner_dept: str = "销售部"
    period_kind: str
    period_key: str
    targets: dict[str, float | int | str]


class GoalSplitIn(BaseModel):
    owner_sales: str
    year: int
    month: int | None = None


class GoalDeleteIn(BaseModel):
    owner_sales: str
    year: int


class GoalYearSaveIn(BaseModel):
    owner_sales: str
    owner_dept: str = "销售部"
    year: int
    targets: dict[str, float | int | str]
    auto_split: bool = True


class SeaAssignIn(BaseModel):
    codes: list[str]
    owner_sales: str


class FollowIn(BaseModel):
    record_type: str = "客户"
    content: str
    customer_code: str | None = None
    lead_code: str | None = None
    opportunity_id: int | None = None
    next_follow_date: date | None = None


class FieldVisitIn(BaseModel):
    title: str = "外勤拜访"
    visit_plan: str = ""
    customer_code: str | None = None
    customer_name: str = ""
    visit_kind: str = "老客户拜访"
    expected_address: str = ""
    before_note: str = ""
    situation_note: str = ""


class FieldVisitPatchIn(BaseModel):
    title: str | None = None
    visit_plan: str | None = None
    customer_code: str | None = None
    customer_name: str | None = None
    visit_kind: str | None = None
    expected_address: str | None = None
    before_note: str | None = None
    situation_note: str | None = None
    photo_note: str | None = None


class FieldVisitParseIn(BaseModel):
    raw_text: str = ""


class FieldVisitConfirmIn(BaseModel):
    create_customer: bool = False
    customer_code: str | None = None
    lead_code: str | None = None
    confirm_opportunity: bool = False
    opp_name: str | None = None
    opp_amount: float | None = None


class FieldVisitLogIn(BaseModel):
    body: str = ""


class FieldVisitFinalizeIn(BaseModel):
    prefer_llm: bool = True


class LeadConvertIn(BaseModel):
    convert_note: str = ""


class LeadOppIn(BaseModel):
    name: str = ""
    amount: float = 0


class LeadLoseIn(BaseModel):
    reason: str


class CollaboratorsIn(BaseModel):
    names: list[str] = Field(default_factory=list)


class OpportunityCreateIn(BaseModel):
    customer_code: str
    name: str = ""
    amount: float = 0
    expect_close_date: date | None = None


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

    @app.get("/api/crm/customers/mine")
    def crm_customers_mine(
        industry: str | None = None,
        status_tab: str | None = None,
        code: str | None = None,
        contact: str | None = None,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        ensure_demo_customer_portal(db)
        ensure_demo_follows(db)
        return {
            "code": 0,
            "message": "",
            "data": list_mine(
                db,
                role=role,
                actor=_actor(role, x_demo_user),
                today=today or date(2026, 9, 15),
                industry=industry,
                status_tab=status_tab,
                code=code,
                contact=contact,
            ),
        }

    @app.get("/api/crm/customers/{code}")
    def crm_customer_one(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        from db.qc_seed import ensure_qc_seed

        ensure_qc_seed(db)
        data = customer_detail(db, code, role=role, actor=_actor(role, x_demo_user))
        if data is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/crm/sea")
    def crm_sea_list(
        pool_name: str | None = None,
        contact: str | None = None,
        customer_type: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        ensure_demo_customer_portal(db)
        return {
            "code": 0,
            "message": "",
            "data": list_sea(
                db,
                role=role,
                actor=_actor(role, x_demo_user),
                pool_name=pool_name,
                contact=contact,
                customer_type=customer_type,
            ),
        }

    @app.post("/api/crm/sea/claim")
    def crm_sea_claim(
        body: LeadAssignBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES", "SALES_ASSIST"):
            raise HTTPException(status_code=403, detail="无权领取")
        ensure_demo_crm(db)
        actor = _actor(role, x_demo_user)
        if role in ("GM", "SALES_MGR") and body.owner_sales.strip():
            n = assign_sea(db, codes=body.codes, owner_sales=body.owner_sales.strip())
        else:
            n = claim_sea(db, codes=body.codes, actor=actor)
        db.commit()
        return {"code": 0, "message": f"已处理 {n} 条", "data": {"count": n}}

    @app.post("/api/crm/customers/{code}/close")
    def crm_customer_close(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            close_customer(db, code=code, actor=_actor(role, x_demo_user), role=role)
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已关闭", "data": {}}

    @app.post("/api/crm/customers/{code}/collaborators")
    def crm_customer_collaborators(
        code: str,
        body: CollaboratorsIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            set_collaborators(
                db,
                code=code,
                names=body.names,
                actor=_actor(role, x_demo_user),
                role=role,
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "协作人已更新", "data": {}}

    @app.get("/api/crm/follows")
    def crm_follows_list(
        customer_code: str | None = None,
        lead_code: str | None = None,
        opportunity_id: int | None = None,
        record_type: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        ensure_demo_follows(db)
        return {
            "code": 0,
            "message": "",
            "data": list_follows(
                db,
                role=role,
                actor=_actor(role, x_demo_user),
                customer_code=customer_code,
                lead_code=lead_code,
                opportunity_id=opportunity_id,
                record_type=record_type,
            ),
        }

    @app.post("/api/crm/follows")
    def crm_follows_add(
        body: FollowIn,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            row = add_follow(
                db,
                actor=_actor(role, x_demo_user),
                record_type=body.record_type,
                content=body.content,
                customer_code=body.customer_code,
                lead_code=body.lead_code,
                opportunity_id=body.opportunity_id,
                next_follow_date=body.next_follow_date,
                today=today or date(2026, 9, 15),
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已保存", "data": row}

    @app.get("/api/crm/checkin")
    def crm_checkin_list(
        today: date | None = None,
        tag: str | None = None,
        not_meeting_only: bool = False,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        ensure_demo_field_visits(db)
        anchor = today or date(2026, 9, 15)
        return {
            "code": 0,
            "message": "",
            "data": list_field_visits(
                db,
                role=role,
                actor=_actor(role, x_demo_user),
                today=anchor,
                tag=tag,
                not_meeting_only=not_meeting_only,
            ),
        }

    @app.get("/api/crm/checkin/stats")
    def crm_checkin_stats(
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        ensure_demo_field_visits(db)
        anchor = today or date(2026, 9, 15)
        return {
            "code": 0,
            "message": "",
            "data": list_field_visit_stats(
                db, role=role, actor=_actor(role, x_demo_user), today=anchor
            ),
        }

    @app.get("/api/crm/checkin/{code}")
    def crm_checkin_one(
        code: str,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        data = get_field_visit(db, code, today=today or date(2026, 9, 15))
        if data is None:
            raise HTTPException(status_code=404, detail="外勤单不存在")
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/checkin")
    def crm_checkin_create(
        body: FieldVisitIn,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES", "SALES_MGR", "SALES_ASSIST"):
            raise HTTPException(status_code=403, detail="无权新建外勤")
        ensure_demo_crm(db)
        anchor = today or date(2026, 9, 15)
        data = create_field_visit(
            db,
            actor=_actor(role, x_demo_user),
            payload=body.model_dump(),
            today=anchor,
        )
        db.commit()
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/checkin/{code}/sign-in")
    def crm_checkin_sign_in(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            data = check_in(db, code=code, actor=_actor(role, x_demo_user))
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已签到", "data": data}

    @app.post("/api/crm/checkin/{code}/sign-out")
    def crm_checkin_sign_out(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            data = check_out(db, code=code, actor=_actor(role, x_demo_user))
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已签退", "data": data}

    @app.patch("/api/crm/checkin/{code}")
    def crm_checkin_patch(
        code: str,
        body: FieldVisitPatchIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        payload = {k: v for k, v in body.model_dump().items() if v is not None}
        try:
            data = update_field_visit(db, code=code, actor=_actor(role, x_demo_user), payload=payload)
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/checkin/{code}/parse")
    def crm_checkin_parse(
        code: str,
        body: FieldVisitParseIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        row = get_field_visit(db, code)
        if row is None:
            raise HTTPException(status_code=404, detail="外勤单不存在")
        raw = body.raw_text or timeline_text(db, code) or row.get("situation_note") or ""
        actor = _actor(role, x_demo_user)
        matches = match_customers_and_leads(
            db,
            actor=actor,
            text=raw,
            customer_name=row.get("customer_name") or "",
        )
        return {
            "code": 0,
            "message": "",
            "data": {"parsed": parse_situation_note(raw), **matches},
        }

    @app.post("/api/crm/checkin/{code}/logs")
    def crm_checkin_add_log(
        code: str,
        body: FieldVisitLogIn,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            data = add_field_visit_log(
                db,
                code=code,
                body=body.body,
                actor=_actor(role, x_demo_user),
                today=today or date(2026, 9, 15),
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已追加", "data": data}

    @app.post("/api/crm/checkin/{code}/finalize")
    def crm_checkin_finalize(
        code: str,
        body: FieldVisitFinalizeIn | None = None,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        opts = body or FieldVisitFinalizeIn()
        try:
            data = finalize_field_visit(
                db,
                code=code,
                today=today or date(2026, 9, 15),
                prefer_llm=opts.prefer_llm,
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已归纳", "data": data}

    @app.post("/api/crm/checkin/{code}/confirm-follow")
    def crm_checkin_confirm_follow(
        code: str,
        body: FieldVisitConfirmIn | None = None,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        opts = body or FieldVisitConfirmIn()
        try:
            data = confirm_field_visit_follow(
                db,
                code=code,
                actor=_actor(role, x_demo_user),
                today=today or date(2026, 9, 15),
                create_customer=opts.create_customer,
                customer_code=opts.customer_code,
                lead_code=opts.lead_code,
                confirm_opportunity=opts.confirm_opportunity,
                opp_name=opts.opp_name,
                opp_amount=opts.opp_amount,
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已写入跟进", "data": data}

    @app.get("/api/crm/payment-plans")
    def crm_payment_plans(
        order_no: str | None = None,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": list_payment_plan_menu(
                db,
                role=role,
                actor=_actor(role, x_demo_user),
                order_no=order_no,
                today=today or date(2026, 9, 15),
            ),
        }

    @app.get("/api/crm/leads/report")
    def crm_leads_report(
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": lead_report(
                db,
                role=role,
                actor=_actor(role, x_demo_user),
                today=today or date(2026, 9, 15),
            ),
        }

    @app.get("/api/crm/leads/report/drill")
    def crm_leads_report_drill(
        bucket: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": leads_for_drill(db, role=role, actor=_actor(role, x_demo_user), bucket=bucket),
        }

    @app.get("/api/crm/orders/{order_no}/sales-360")
    def crm_order_sales_360(
        order_no: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        data = order_360(db, order_no)
        if data is None:
            raise HTTPException(status_code=404, detail="订单不存在")
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/crm/quotes/{code}/print")
    def crm_quote_print(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            html = quote_print_html(db, code)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return Response(content=html, media_type="text/html; charset=utf-8")

    @app.get("/api/crm/quotes/{code}/pdf")
    def crm_quote_pdf(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            body, filename = quote_pdf_bytes(db, code)
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        return Response(content=body, media_type="application/pdf", headers=headers)

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

    @app.get("/api/crm/opportunities/funnel")
    def crm_opportunities_funnel(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        from db.crm_opportunity_ui import opportunity_funnel

        role = _role(x_demo_role)
        ensure_demo_crm(db)
        ensure_sales_pack(db)
        return {
            "code": 0,
            "message": "",
            "data": opportunity_funnel(
                db, role=role, owner_filter=_sales_filter(role, x_demo_user)
            ),
        }

    @app.get("/api/crm/opportunities/{opp_id}")
    def crm_opportunity_one(
        opp_id: int,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            data = present_opportunity(db, opp_id, role=role, actor=_actor(role, x_demo_user))
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        if data is None:
            raise HTTPException(status_code=404, detail="商机不存在")
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/crm/opportunities")
    def crm_opportunities(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        ensure_sales_pack(db)
        return {
            "code": 0,
            "message": "",
            "data": list_opportunities(
                db, role=role, owner_filter=_sales_filter(role, x_demo_user)
            ),
        }

    @app.post("/api/crm/opportunities")
    def crm_opportunity_create(
        body: OpportunityCreateIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES", "SALES_ASSIST"):
            raise HTTPException(status_code=403, detail="无权新建商机")
        ensure_demo_crm(db)
        actor = _actor(role, x_demo_user)
        try:
            data = create_opportunity_for_customer(
                db,
                customer_code=body.customer_code.strip(),
                name=body.name,
                amount=body.amount,
                owner_sales=actor,
                expect_close_date=body.expect_close_date,
                actor=actor,
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "商机已创建", "data": data}

    @app.get("/api/crm/board")
    def crm_board(
        include_all: bool = False,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": sales_board(
                db, role=role, actor=_actor(role, x_demo_user), include_all=include_all
            ),
        }

    @app.get("/api/crm/mobile/customers")
    def crm_mobile_customers(
        q: str = "",
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": mobile_customers(db, role=role, actor=_actor(role, x_demo_user), query=q),
        }

    @app.get("/api/crm/mobile/customers/{code}")
    def crm_mobile_customer(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            data = mobile_customer(db, role=role, actor=_actor(role, x_demo_user), code=code)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        if data is None:
            raise HTTPException(status_code=404, detail="客户不存在")
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/crm/mobile/orders")
    def crm_mobile_orders(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": mobile_orders(db, role=role, actor=_actor(role, x_demo_user)),
        }

    @app.get("/api/crm/visits/home")
    def crm_visit_home(
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        return {
            "code": 0,
            "message": "",
            "data": home_for(db, role=role, actor=_actor(role, x_demo_user), today=today or date(2026, 9, 15)),
        }

    @app.post("/api/crm/visits/draft")
    def crm_visit_draft(
        body: VisitDraftIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES", "SALES_MGR", "SALES_ASSIST"):
            raise HTTPException(status_code=403, detail="无权起草拜访")
        ensure_demo_crm(db)
        ensure_sales_pack(db)
        return {
            "code": 0,
            "message": "",
            "data": build_draft(db, body.text, today=body.today or date(2026, 9, 15)),
        }

    @app.post("/api/crm/visits/confirm")
    def crm_visit_confirm(
        body: VisitConfirmIn,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES", "SALES_MGR", "SALES_ASSIST"):
            raise HTTPException(status_code=403, detail="无权确认拜访")
        ensure_demo_crm(db)
        try:
            data = confirm_visit(
                db,
                actor=_actor(role, x_demo_user),
                payload=body.model_dump(),
                today=today or date(2026, 9, 15),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/opportunities/{opp_id}/grade")
    def crm_opportunity_grade(
        opp_id: int,
        body: GradeIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="只有销管或总经理能标级")
        ensure_demo_crm(db)
        ensure_sales_pack(db)
        try:
            data = grade_opportunity(db, opp_id, body.grade)
        except KeyError:
            raise HTTPException(status_code=404, detail="商机不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/opportunities/{opp_id}/lose")
    def crm_opportunity_lose(
        opp_id: int,
        body: LoseIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES", "SALES_MGR", "SALES_ASSIST"):
            raise HTTPException(status_code=403, detail="无权标丢单")
        ensure_demo_crm(db)
        try:
            lose_opportunity(db, opp_id, body.reason)
        except KeyError:
            raise HTTPException(status_code=404, detail="商机不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "", "data": {"lost_reason": body.reason}}

    @app.post("/api/crm/opportunities/{opp_id}/sample-cost")
    def crm_opportunity_sample_cost(
        opp_id: int,
        body: SampleCostIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "RD", "FIN"):
            raise HTTPException(status_code=403, detail="无权填打样成本")
        ensure_demo_crm(db)
        try:
            set_sample_cost(db, opp_id, qty=body.qty, material=body.material, labor=body.labor_overhead)
        except KeyError:
            raise HTTPException(status_code=404, detail="商机不存在") from None
        return {"code": 0, "message": "", "data": {"id": opp_id}}

    @app.post("/api/crm/opportunities/{opp_id}/customer-quote")
    def crm_opportunity_customer_quote(
        opp_id: int,
        body: MoneyIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "FIN"):
            raise HTTPException(status_code=403, detail="无权填对客报价")
        ensure_demo_crm(db)
        try:
            set_customer_quote(db, opp_id, body.amount)
        except KeyError:
            raise HTTPException(status_code=404, detail="商机不存在") from None
        return {"code": 0, "message": "", "data": {"id": opp_id}}

    @app.post("/api/crm/opportunities/{opp_id}/planned-labor")
    def crm_opportunity_planned_labor(
        opp_id: int,
        body: MoneyIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "FIN"):
            raise HTTPException(status_code=403, detail="无权填计划人工")
        ensure_demo_crm(db)
        try:
            set_planned_labor(db, opp_id, body.amount)
        except KeyError:
            raise HTTPException(status_code=404, detail="商机不存在") from None
        return {"code": 0, "message": "", "data": {"id": opp_id}}

    @app.get("/api/crm/llm-config")
    def crm_llm_config_get(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权查看模型配置")
        return {"code": 0, "message": "", "data": llm_public_config(db)}

    @app.put("/api/crm/llm-config")
    def crm_llm_config_put(
        body: LlmConfigIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role != "GM":
            raise HTTPException(status_code=403, detail="只有总经理能改模型配置")
        return {
            "code": 0,
            "message": "",
            "data": save_llm_config(db, base_url=body.base_url, model=body.model, api_key=body.api_key),
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

    @app.post("/api/crm/samples/{code}/customer-confirm")
    def crm_sample_customer_confirm(
        code: str,
        body: SampleConfirmBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES", "RD"):
            raise HTTPException(status_code=403, detail="无权登记客户确认")
        ensure_demo_crm(db)
        data = sample_detail(db, code)
        if data is None:
            raise HTTPException(status_code=404, detail="样品不存在")
        if role == "SALES" and _sales_filter(role) and data["owner_sales"] != _sales_filter(role):
            raise HTTPException(status_code=403, detail="无权维护该样品")
        try:
            updated = confirm_sample_customer(
                db,
                code,
                passed=body.passed,
                fail_reason=body.fail_reason,
                ship_date=body.ship_date,
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

    @app.post("/api/crm/samples/launch")
    def crm_sample_launch(
        body: SampleLaunchBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("SALES", "SALES_MGR", "GM", "SALES_ASSIST"):
            raise HTTPException(status_code=403, detail="无权发起打样")
        ensure_demo_crm(db)
        from db.crm_samples_ui import launch_sample_flow

        try:
            data = launch_sample_flow(
                db,
                actor=_actor(role, x_demo_user),
                opportunity_id=body.opportunity_id,
                due_date=body.due_date,
                item_draft_name=body.item_draft_name,
                start_date=body.start_date,
                submit=body.submit,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        db.commit()
        return {"code": 0, "message": "", "data": data}

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
        ui_tab: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES", "FIN", "PMC"):
            raise HTTPException(status_code=403, detail="无权查看报价")
        ensure_demo_crm(db)
        hide = role == "WH"
        rows = list_quotes(db, customer_code=customer_code, status=status, hide_amount=hide)
        if ui_tab:
            rows = filter_quotes_by_tab(rows, ui_tab)
        return {
            "code": 0,
            "message": "",
            "data": rows,
            "tab_counts": quote_tab_counts(
                list_quotes(db, customer_code=customer_code, status=status, hide_amount=hide)
            ),
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

    @app.post("/api/crm/quotes/{code}/requote")
    def crm_quote_requote(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权退回报价")
        ensure_demo_crm(db)
        try:
            data = mark_requote(db, code)
            db.commit()
        except KeyError:
            raise HTTPException(status_code=404, detail="报价单不存在") from None
        return {"code": 0, "message": "已标记需重新报价", "data": data}

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

    @app.get("/api/crm/goals/owners")
    def crm_goal_owners(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权查看目标人员")
        ensure_demo_crm(db)
        return {"code": 0, "message": "", "data": list_goal_owner_candidates(db)}

    @app.get("/api/crm/goals/periods")
    def crm_goal_periods_list(
        year: int = 2026,
        month_from: int | None = None,
        month_to: int | None = None,
        owner_sales: str | None = None,
        owner_dept: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "SALES"):
            raise HTTPException(status_code=403, detail="无权查看目标")
        ensure_demo_crm(db)
        ensure_demo_goal_period(db)
        return {
            "code": 0,
            "message": "",
            "data": list_goal_tree(
                db,
                year=year,
                month_from=month_from,
                month_to=month_to,
                owner_sales=owner_sales,
                owner_dept=owner_dept,
                role=role,
                actor=_actor(role, x_demo_user),
            ),
        }

    @app.post("/api/crm/goals/year")
    def crm_goal_year_save(
        body: GoalYearSaveIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权维护目标")
        ensure_demo_crm(db)
        owner = body.owner_sales.strip()
        if not owner:
            raise HTTPException(status_code=400, detail="请填写目标人")
        try:
            save_year_and_split(
                db,
                owner=owner,
                dept=body.owner_dept.strip() or "销售部",
                year=body.year,
                targets=body.targets,
                actor=_actor(role, x_demo_user),
                auto_split=body.auto_split,
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        msg = "已保存并拆到月/周" if body.auto_split else "已保存年目标"
        return {"code": 0, "message": msg, "data": {"period_key": year_key(body.year)}}

    @app.post("/api/crm/goals/periods")
    def crm_goal_periods_save(
        body: GoalPeriodSaveIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权维护目标")
        ensure_demo_crm(db)
        try:
            save_period_targets(
                db,
                owner=body.owner_sales,
                dept=body.owner_dept,
                kind=body.period_kind,
                key=body.period_key,
                targets=body.targets,
                actor=_actor(role, x_demo_user),
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已保存", "data": {}}

    @app.post("/api/crm/goals/split")
    def crm_goal_split(
        body: GoalSplitIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权拆分目标")
        ensure_demo_crm(db)
        actor = _actor(role, x_demo_user)
        try:
            if body.month is None:
                split_year_to_months(db, owner=body.owner_sales, year=body.year, actor=actor)
                reapply_demo_week_bump(db, owner=body.owner_sales, year=body.year)
            else:
                split_month_to_weeks(db, owner=body.owner_sales, year=body.year, month=body.month, actor=actor)
                if body.month == 9:
                    reapply_demo_week_bump(db, owner=body.owner_sales, year=body.year)
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已拆分", "data": {}}

    @app.delete("/api/crm/goals/periods")
    def crm_goal_periods_delete(
        owner_sales: str,
        year: int,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权删除目标")
        ensure_demo_crm(db)
        delete_year_goal(db, owner=owner_sales, year=year)
        db.commit()
        return {"code": 0, "message": "已删除", "data": {}}

    @app.get("/api/crm/contracted-progress")
    def crm_contracted_progress(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        return {"code": 0, "message": "", "data": list_contracted_progress(db, role=role)}

    @app.get("/api/crm/leads")
    def crm_leads_list(
        pool: bool = False,
        contact: str | None = None,
        phone: str | None = None,
        status: str | None = None,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        actor = _sales_filter(role) or ""
        if pool and role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权查看线索池")
        return {
            "code": 0,
            "message": "",
            "data": list_leads(
                db,
                role=role,
                pool=pool,
                contact=contact,
                phone=phone,
                status=status,
                today=today or date(2026, 9, 15),
            ),
        }

    @app.get("/api/crm/leads/{code}")
    def crm_lead_detail(
        code: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        row = get_lead(db, code)
        if row is None:
            raise HTTPException(status_code=404, detail="线索不存在")
        return {"code": 0, "message": "", "data": row}

    @app.post("/api/crm/leads")
    def crm_lead_create(
        body: LeadBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        actor = _sales_filter(role) or "演示用户"
        return {"code": 0, "message": "", "data": create_lead(db, body.model_dump(), actor=actor, role=role)}

    @app.post("/api/crm/leads/assign")
    def crm_lead_assign(
        body: LeadAssignBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权分配线索")
        ensure_demo_crm(db)
        actor = _sales_filter(role) or "销管"
        n = assign_leads(db, body.codes, body.owner_sales, actor=actor)
        db.commit()
        return {"code": 0, "message": "", "data": {"assigned": n}}

    @app.post("/api/crm/leads/{code}/follow")
    def crm_lead_follow(
        code: str,
        body: LeadFollowBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        actor = _sales_filter(role) or "李业务"
        try:
            data = add_lead_follow(
                db,
                code,
                content=body.content,
                owner_sales=actor,
                next_follow_date=body.next_follow_date,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        db.commit()
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/crm/leads/{code}/convert-customer")
    def crm_lead_convert_customer(
        code: str,
        body: LeadConvertIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            data = convert_lead_to_customer(
                db,
                code,
                actor=_actor(role, x_demo_user),
                role=role,
                convert_note=body.convert_note,
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已转为客户", "data": data}

    @app.post("/api/crm/leads/{code}/convert-opportunity")
    def crm_lead_convert_opp(
        code: str,
        body: LeadOppIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            data = convert_lead_to_opportunity(
                db,
                code,
                actor=_actor(role, x_demo_user),
                role=role,
                name=body.name,
                amount=body.amount,
            )
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已转为商机", "data": data}

    @app.post("/api/crm/leads/{code}/lose")
    def crm_lead_lose(
        code: str,
        body: LeadLoseIn,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        x_demo_user: str | None = Header(default=None, alias="X-Demo-User"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        try:
            lose_lead(db, code, reason=body.reason, actor=_actor(role, x_demo_user), role=role)
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "已标记丢失", "data": {}}

    @app.get("/api/crm/lead-pool-rules")
    def crm_lead_pool_rules(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权查看线索池规则")
        ensure_demo_crm(db)
        return {"code": 0, "message": "", "data": list_pool_rules(db)}

    @app.post("/api/crm/lead-pool-rules")
    def crm_lead_pool_rule_save(
        body: PoolRuleBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权维护线索池规则")
        ensure_demo_crm(db)
        actor = _sales_filter(role) or "销管"
        data = save_pool_rule(db, body.model_dump(), actor=actor)
        db.commit()
        return {"code": 0, "message": "", "data": data}
