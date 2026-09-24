"""SQLAlchemy 表映射（字段对齐 engine.models / 需求 §5）。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class MdItemRow(Base):
    __tablename__ = "md_item"
    item_code: Mapped[str] = mapped_column(String, primary_key=True)
    item_name: Mapped[str] = mapped_column(String)
    dept: Mapped[str] = mapped_column(String)
    group_code: Mapped[str] = mapped_column(String)
    unit_sale: Mapped[str] = mapped_column(String)
    pcs_per_board: Mapped[int] = mapped_column(Integer)
    board_per_box: Mapped[str] = mapped_column(Numeric(18, 6))
    loss_rate: Mapped[str] = mapped_column(Numeric(18, 6))
    color: Mapped[str] = mapped_column(String)
    is_semi: Mapped[bool] = mapped_column(Boolean)
    computable: Mapped[bool] = mapped_column(Boolean)
    prod_category: Mapped[str] = mapped_column(String, default="")
    kg_per_board: Mapped[str | None] = mapped_column(Numeric(18, 6), nullable=True)
    display_uom: Mapped[str] = mapped_column(String, default="BOARD")


class MdUomConvertRow(Base):
    __tablename__ = "md_uom_convert"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_code: Mapped[str] = mapped_column(String, index=True)
    from_uom: Mapped[str] = mapped_column(String)
    to_uom: Mapped[str] = mapped_column(String)
    factor: Mapped[str] = mapped_column(Numeric(18, 6))


class MdItemRouteRow(Base):
    __tablename__ = "md_item_route"
    item_code: Mapped[str] = mapped_column(String, primary_key=True)
    needs_semi: Mapped[bool] = mapped_column(Boolean)
    semi_item_code: Mapped[str | None] = mapped_column(String, nullable=True)
    semi_board_per_box: Mapped[str | None] = mapped_column(Numeric(18, 6), nullable=True)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    changeover_min: Mapped[int] = mapped_column(Integer)


class MdSphRow(Base):
    __tablename__ = "md_sph"
    item_code: Mapped[str] = mapped_column(String, primary_key=True)
    group_code: Mapped[str] = mapped_column(String, primary_key=True)
    sph_value: Mapped[str] = mapped_column(Numeric(18, 6))
    sph_basis: Mapped[str] = mapped_column(String)
    sph_crew: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sph_uom: Mapped[str] = mapped_column(String)
    crew_std: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String)
    effective_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String)


class MdCapacityCalendarRow(Base):
    __tablename__ = "md_capacity_calendar"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dept: Mapped[str] = mapped_column(String, index=True, default="FINISHED_DEPT")
    group_code: Mapped[str] = mapped_column(String, index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    is_workday: Mapped[bool] = mapped_column(Boolean)
    hours_per_day: Mapped[str] = mapped_column(Numeric(18, 4))
    headcount: Mapped[int] = mapped_column(Integer)
    reserved_ratio: Mapped[str] = mapped_column(Numeric(18, 6))


class StockRow(Base):
    __tablename__ = "stock"
    item_code: Mapped[str] = mapped_column(String, primary_key=True)
    qty_available: Mapped[str] = mapped_column(Numeric(18, 4))
    uom_display: Mapped[str] = mapped_column(String, default="BOARD")
    source: Mapped[str] = mapped_column(String, default="SEED")
    warehouse_code: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MdBomLineRow(Base):
    __tablename__ = "md_bom_line"
    parent_item_code: Mapped[str] = mapped_column(String, primary_key=True)
    line_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_item_code: Mapped[str] = mapped_column(String)
    component_role: Mapped[str] = mapped_column(String)
    qty_per_parent: Mapped[str] = mapped_column(Numeric(18, 6))
    qty_basis_uom: Mapped[str] = mapped_column(String, default="BOX")
    scrap_rate: Mapped[str | None] = mapped_column(Numeric(18, 6), nullable=True)
    offset_days: Mapped[int] = mapped_column(Integer, default=0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=4)
    kit_critical: Mapped[bool] = mapped_column(Boolean, default=True)


class SoOrderLineRow(Base):
    __tablename__ = "so_order_line"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String, index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    item_code: Mapped[str] = mapped_column(String)
    item_name: Mapped[str] = mapped_column(String, default="")
    qty: Mapped[str] = mapped_column(Numeric(18, 4))
    unit: Mapped[str] = mapped_column(String)
    unit_price: Mapped[str] = mapped_column(Numeric(18, 4), default="0")
    line_amount: Mapped[str] = mapped_column(Numeric(18, 2), default="0")
    spec: Mapped[str] = mapped_column(String, default="")
    mold_fee: Mapped[str] = mapped_column(Numeric(18, 2), default="0")
    rebate_qty: Mapped[str | None] = mapped_column(Numeric(18, 4), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


class SoOrderRow(Base):
    __tablename__ = "so_order"
    order_no: Mapped[str] = mapped_column(String, primary_key=True)
    customer: Mapped[str] = mapped_column(String)
    sales_name: Mapped[str] = mapped_column(String, default="")
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    owner_sales: Mapped[str] = mapped_column(String, default="")
    item_code: Mapped[str] = mapped_column(String)
    qty_order: Mapped[str] = mapped_column(Numeric(18, 4))
    unit: Mapped[str] = mapped_column(String)
    due_date: Mapped[date] = mapped_column(Date)
    ready_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    customer_level: Mapped[int] = mapped_column(Integer)
    amount: Mapped[str] = mapped_column(Numeric(18, 2))
    is_urgent: Mapped[bool] = mapped_column(Boolean)
    schedule_phase: Mapped[str] = mapped_column(String, default="PENDING")
    order_status: Mapped[str] = mapped_column(String, default="CONFIRMED")
    kitting_rate_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_source: Mapped[str] = mapped_column(String, default="MANUAL")
    contract_no: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    quote_no: Mapped[str | None] = mapped_column(String, nullable=True, index=True)


class KingdeeSyncLogRow(Base):
    __tablename__ = "kingdee_sync_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direction: Mapped[str] = mapped_column(String, default="PUSH_IN")
    doc_type: Mapped[str] = mapped_column(String)
    doc_no: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class AuditLogRow(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_role: Mapped[str] = mapped_column(String)
    actor_name: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    action: Mapped[str] = mapped_column(String)
    before_json: Mapped[str] = mapped_column(Text, default="{}")
    after_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class CrmCustomerRow(Base):
    __tablename__ = "crm_customer"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    channel_l1: Mapped[str] = mapped_column(String)
    channel_l2: Mapped[str] = mapped_column(String)
    owner_sales: Mapped[str] = mapped_column(String)
    level: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    custom_fields_json: Mapped[str] = mapped_column(Text, default="{}")
    duplicate_flag: Mapped[bool] = mapped_column(Boolean, default=False)


class CrmOpportunityRow(Base):
    __tablename__ = "crm_opportunity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    customer_code: Mapped[str] = mapped_column(String, index=True)
    stage: Mapped[str] = mapped_column(String)
    amount: Mapped[str] = mapped_column(Numeric(18, 2))
    owner_sales: Mapped[str] = mapped_column(String)
    expect_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sample_code: Mapped[str | None] = mapped_column(String, nullable=True)
    grade: Mapped[str | None] = mapped_column(String, nullable=True)
    lost_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    project_code: Mapped[str | None] = mapped_column(String, nullable=True)
    sample_cost_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_cost_material: Mapped[str | None] = mapped_column(Numeric(18, 2), nullable=True)
    sample_cost_labor: Mapped[str | None] = mapped_column(Numeric(18, 2), nullable=True)
    planned_labor_amount: Mapped[str | None] = mapped_column(Numeric(18, 2), nullable=True)
    customer_quote_amount: Mapped[str | None] = mapped_column(Numeric(18, 2), nullable=True)
    urgent_order_no: Mapped[str | None] = mapped_column(String, nullable=True)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")


class CrmSampleStepRow(Base):
    __tablename__ = "crm_sample_step"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sample_code: Mapped[str] = mapped_column(String, index=True)
    step_no: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String)
    event_date: Mapped[date] = mapped_column(Date)
    product_desc: Mapped[str] = mapped_column(String, default="")
    situation_desc: Mapped[str] = mapped_column(Text, default="")
    evidence_text: Mapped[str] = mapped_column(Text, default="")
    evidence_images_json: Mapped[str] = mapped_column(Text, default="[]")
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    round_no: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CrmSampleRow(Base):
    __tablename__ = "crm_sample"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    customer_code: Mapped[str] = mapped_column(String, index=True)
    item_draft_name: Mapped[str] = mapped_column(String)
    current_stage: Mapped[str] = mapped_column(String)
    round_no: Mapped[int] = mapped_column(Integer, default=1)
    owner_sales: Mapped[str] = mapped_column(String)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_old_product: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_passed: Mapped[str | None] = mapped_column(String, nullable=True)
    fail_reason: Mapped[str] = mapped_column(String, default="")
    ship_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class PlanVersionRow(Base):
    __tablename__ = "plan_version"
    version_no: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    trigger: Mapped[str] = mapped_column(String)
    snapshot_hash: Mapped[str] = mapped_column(String, default="")
    conflicts_json: Mapped[str] = mapped_column(Text, default="[]")
    kit_json: Mapped[str] = mapped_column(Text, default="{}")


class WoRow(Base):
    __tablename__ = "wo"
    wo_no: Mapped[str] = mapped_column(String, primary_key=True)
    wo_type: Mapped[str] = mapped_column(String)
    source_order_no: Mapped[str] = mapped_column(String, index=True)
    item_code: Mapped[str] = mapped_column(String)
    group_code: Mapped[str] = mapped_column(String)
    dept: Mapped[str] = mapped_column(String)
    qty_order: Mapped[str] = mapped_column(Numeric(18, 4))
    qty_board_plan: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    plan_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    plan_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    earliest_start: Mapped[date] = mapped_column(Date)
    crew_plan: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_version: Mapped[int] = mapped_column(Integer, index=True)
    parent_wo_no: Mapped[str | None] = mapped_column(String, nullable=True)
    qty_board_done: Mapped[int] = mapped_column(Integer, default=0)


class WoTaskRow(Base):
    __tablename__ = "wo_task"
    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wo_no: Mapped[str] = mapped_column(String, index=True)
    dept: Mapped[str] = mapped_column(String, default="FINISHED_DEPT")
    group_code: Mapped[str] = mapped_column(String)
    task_date: Mapped[date] = mapped_column(Date)
    qty_board: Mapped[int] = mapped_column(Integer)
    hours_wall: Mapped[str] = mapped_column(Numeric(18, 4))
    hours_man: Mapped[str] = mapped_column(Numeric(18, 4))
    crew_plan: Mapped[int] = mapped_column(Integer)
    seq: Mapped[int] = mapped_column(Integer)
    changeover_min: Mapped[int] = mapped_column(Integer, default=0)
    plan_version: Mapped[int] = mapped_column(Integer, index=True)
    qty_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kg_per_board_snap: Mapped[str | None] = mapped_column(Numeric(18, 6), nullable=True)


class WoDependencyRow(Base):
    __tablename__ = "wo_dependency"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pred_wo_no: Mapped[str] = mapped_column(String)
    succ_wo_no: Mapped[str] = mapped_column(String)
    dep_type: Mapped[str] = mapped_column(String, default="FS")
    offset_days: Mapped[int] = mapped_column(Integer)


class WoInsertLogRow(Base):
    __tablename__ = "wo_insert_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wo_no: Mapped[str] = mapped_column(String)
    requester: Mapped[str] = mapped_column(String)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String)
    strategy: Mapped[str | None] = mapped_column(String, nullable=True)
    cost_json: Mapped[str] = mapped_column(Text, default="{}")
    plan_version_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_version_after: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CrmContractRow(Base):
    __tablename__ = "crm_contract"
    contract_no: Mapped[str] = mapped_column(String, primary_key=True)
    customer_code: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="DRAFT")
    contract_amount: Mapped[str] = mapped_column(Numeric(18, 2))
    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String, default="CNY")
    opportunity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_sales: Mapped[str] = mapped_column(String, default="")
    terms_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class CrmContractPaymentPlanRow(Base):
    __tablename__ = "crm_contract_payment_plan"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_no: Mapped[str] = mapped_column(String, index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    milestone: Mapped[str] = mapped_column(String, default="")
    condition_type: Mapped[str] = mapped_column(String, default="CUSTOM")
    condition_note: Mapped[str] = mapped_column(Text, default="")
    plan_date: Mapped[date] = mapped_column(Date)
    plan_amount: Mapped[str] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String, default="OPEN")


class CrmPaymentReceiptRow(Base):
    __tablename__ = "crm_payment_receipt"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_no: Mapped[str] = mapped_column(String, index=True)
    plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    receipt_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[str] = mapped_column(Numeric(18, 2))
    method: Mapped[str] = mapped_column(String, default="银行转账")
    ref_no: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="CONFIRMED")
    note: Mapped[str] = mapped_column(Text, default="")


class CrmQuoteRow(Base):
    __tablename__ = "crm_quote"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    customer_code: Mapped[str] = mapped_column(String, index=True)
    sample_code: Mapped[str | None] = mapped_column(String, nullable=True)
    total_amount: Mapped[str] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String, default="DRAFT")
    owner_sales: Mapped[str] = mapped_column(String, default="")
    lines_json: Mapped[str] = mapped_column(Text, default="[]")
    opportunity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_rate: Mapped[str] = mapped_column(Numeric(18, 4), default="0.13")
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_no: Mapped[str | None] = mapped_column(String, nullable=True)
    order_no: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    note: Mapped[str] = mapped_column(Text, default="")


class CrmQuoteLineRow(Base):
    __tablename__ = "crm_quote_line"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quote_code: Mapped[str] = mapped_column(String, index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    item_code: Mapped[str | None] = mapped_column(String, nullable=True)
    item_name: Mapped[str] = mapped_column(String, default="")
    image_ref: Mapped[str] = mapped_column(Text, default="")
    spec: Mapped[str] = mapped_column(String, default="")
    process_label: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String, default="")
    unit_price_tax_in: Mapped[str] = mapped_column(Numeric(18, 4), default="0")
    moq: Mapped[str | None] = mapped_column(Numeric(18, 4), nullable=True)
    qty: Mapped[str] = mapped_column(Numeric(18, 4))
    uom: Mapped[str] = mapped_column(String, default="BOX")
    mold_fee: Mapped[str] = mapped_column(Numeric(18, 2), default="0")
    rebate_qty: Mapped[str | None] = mapped_column(Numeric(18, 4), nullable=True)
    rebate_uom: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


class OrderChangeRequestRow(Base):
    __tablename__ = "order_change_request"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String, index=True)
    change_type: Mapped[str] = mapped_column(String)
    old_value_json: Mapped[str] = mapped_column(Text, default="{}")
    new_value_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String, default="PENDING")
    requested_by: Mapped[str] = mapped_column(String, default="")
    requested_role: Mapped[str] = mapped_column(String, default="")
    impact_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String, default="SALES_CHANGE")
    suggested_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    sales_proposed_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    brief_text: Mapped[str] = mapped_column(Text, default="")
    run_id: Mapped[str] = mapped_column(String, default="")


class SoOrderDueEventRow(Base):
    __tablename__ = "so_order_due_event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    actor_role: Mapped[str] = mapped_column(String, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    run_id: Mapped[str] = mapped_column(String, default="")
    change_request_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class WecomMessageRow(Base):
    __tablename__ = "wecom_message"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, default="")
    deep_link: Mapped[str] = mapped_column(String, default="/portal")
    role_targets_json: Mapped[str] = mapped_column(Text, default="[]")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class WecomScheduleEventRow(Base):
    __tablename__ = "wecom_schedule_event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scene: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deep_link: Mapped[str] = mapped_column(String, default="/schedule")
    idempotency_key: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class HrEmployeeRow(Base):
    __tablename__ = "hr_employee"
    emp_no: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    department: Mapped[str] = mapped_column(String, index=True)
    position: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    hired_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employee_kind: Mapped[str] = mapped_column(String, default="STAFF")
    is_team_leader: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_dept: Mapped[str | None] = mapped_column(String, nullable=True)
    group_code: Mapped[str | None] = mapped_column(String, nullable=True)
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_remind_days: Mapped[int] = mapped_column(Integer, default=30)


class HrLaborRateRow(Base):
    __tablename__ = "hr_labor_rate"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_dept: Mapped[str] = mapped_column(String)
    group_code: Mapped[str] = mapped_column(String)
    rate_per_man_hour: Mapped[str] = mapped_column(Numeric(18, 4))
    effective_from: Mapped[date] = mapped_column(Date)


class ProdTimeReportRow(Base):
    __tablename__ = "prod_time_report"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    schedule_dept: Mapped[str] = mapped_column(String)
    group_code: Mapped[str] = mapped_column(String)
    plan_version: Mapped[int] = mapped_column(Integer)
    hours_man_planned: Mapped[str] = mapped_column(Numeric(18, 4))
    hours_man_actual: Mapped[str | None] = mapped_column(Numeric(18, 4), nullable=True)
    headcount_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="DRAFT")
    reported_by: Mapped[str] = mapped_column(String, default="")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    hours_normal: Mapped[str | None] = mapped_column(Numeric(18, 4), nullable=True)
    hours_ot: Mapped[str | None] = mapped_column(Numeric(18, 4), nullable=True)
    headcount_indirect: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hours_indirect_normal: Mapped[str | None] = mapped_column(Numeric(18, 4), nullable=True)
    hours_indirect_ot: Mapped[str | None] = mapped_column(Numeric(18, 4), nullable=True)


class HrGroupAttendanceRow(Base):
    """组×日出勤实到（考勤机汇总或人工覆盖，供排程读 headcount_present）。"""

    __tablename__ = "hr_group_attendance"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schedule_dept: Mapped[str] = mapped_column(String, index=True)
    group_code: Mapped[str] = mapped_column(String, index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    headcount_present: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String, default="PUNCH")
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class HrAttendancePunchRow(Base):
    __tablename__ = "hr_attendance_punch"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    emp_no: Mapped[str] = mapped_column(String, index=True)
    punch_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    punch_type: Mapped[str] = mapped_column(String)
    device_code: Mapped[str] = mapped_column(String)
    device_name: Mapped[str] = mapped_column(String)
    synced_at: Mapped[datetime] = mapped_column(DateTime)


class AppSettingRow(Base):
    __tablename__ = "app_setting"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class DemoRunRow(Base):
    __tablename__ = "demo_run"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="DRAFT")
    path_template: Mapped[str] = mapped_column(String, default="full_chain_17")
    current_step_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by_role: Mapped[str] = mapped_column(String, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class DemoRunSeedEventRow(Base):
    __tablename__ = "demo_run_seed_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    step_id: Mapped[str] = mapped_column(String, index=True)
    batch_index: Mapped[int] = mapped_column(Integer, default=1)
    refs_json: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str] = mapped_column(Text, default="")
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    actor_role: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class DemoRunFeedbackRow(Base):
    __tablename__ = "demo_run_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    step_id: Mapped[str] = mapped_column(String, index=True)
    story_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    expectation: Mapped[str] = mapped_column(Text, default="")
    refs_json: Mapped[str] = mapped_column(Text, default="[]")
    seed_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reporter_role: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class DemoRunStepSnapshotRow(Base):
    """演示结束后每环节最终数据快照（重放只读）。"""

    __tablename__ = "demo_run_step_snapshot"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    step_id: Mapped[str] = mapped_column(String, primary_key=True)
    refs_json: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str] = mapped_column(Text, default="")
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    seed_event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seeded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime)


class ProdQtyReportRow(Base):
    """工单完工版数报工（Wave 2）。"""

    __tablename__ = "prod_qty_report"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wo_no: Mapped[str] = mapped_column(String, index=True)
    work_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qty_board_done: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="CONFIRMED")
    reported_by: Mapped[str] = mapped_column(String, default="")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    plan_version: Mapped[int] = mapped_column(Integer, default=0)


class PendingRollRow(Base):
    """未完版数待确认池：PMC 并入同品项下次或插单，禁止取消尾数。"""

    __tablename__ = "pending_roll_pool"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_wo_no: Mapped[str] = mapped_column(String, index=True)
    source_order_no: Mapped[str] = mapped_column(String, index=True)
    item_code: Mapped[str] = mapped_column(String, index=True)
    group_code: Mapped[str] = mapped_column(String)
    dept: Mapped[str] = mapped_column(String)
    qty_board_remain: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String, default="PENDING_CONFIRMATION", index=True)
    action: Mapped[str | None] = mapped_column(String, nullable=True)
    target_order_no: Mapped[str | None] = mapped_column(String, nullable=True)
    remainder_wo_no: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)


# --- M9 品控台账 ---


class MdSupplierRow(Base):
    __tablename__ = "md_supplier"
    supplier_code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    name_alias: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    kingdee_id: Mapped[str | None] = mapped_column(String, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String, default="KINGDEE")


class MdRawMaterialRow(Base):
    __tablename__ = "md_raw_material"
    material_code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    spec: Mapped[str] = mapped_column(String, default="")
    default_uom: Mapped[str] = mapped_column(String, default="KG")
    attr_default: Mapped[str] = mapped_column(String, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    kingdee_id: Mapped[str | None] = mapped_column(String, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String, default="KINGDEE")


class QcAttachmentRow(Base):
    __tablename__ = "qc_attachment"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    sort_no: Mapped[int] = mapped_column(Integer, default=0)
    file_name: Mapped[str] = mapped_column(String, default="")
    mime_type: Mapped[str] = mapped_column(String, default="image/png")
    storage_kind: Mapped[str] = mapped_column(String, default="INLINE_B64")
    storage_ref: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(String, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)
    uploaded_by: Mapped[str] = mapped_column(String, default="")


class QcMaterialReceiptRow(Base):
    __tablename__ = "qc_material_receipt"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receipt_no: Mapped[str] = mapped_column(String, unique=True, index=True)
    incoming_date: Mapped[date] = mapped_column(Date, index=True)
    month_key: Mapped[str] = mapped_column(String, index=True)
    material_code: Mapped[str] = mapped_column(String, index=True)
    material_name: Mapped[str] = mapped_column(String)
    spec: Mapped[str] = mapped_column(String, default="")
    attr: Mapped[str] = mapped_column(String, default="")
    batch_no: Mapped[str] = mapped_column(String, default="")
    shelf_life_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    shelf_life_text: Mapped[str] = mapped_column(String, default="")
    supplier_code: Mapped[str] = mapped_column(String, index=True)
    supplier_name: Mapped[str] = mapped_column(String)
    qty: Mapped[str] = mapped_column(Numeric(18, 4))
    uom: Mapped[str] = mapped_column(String)
    remark: Mapped[str] = mapped_column(Text, default="")
    kingdee_doc_no: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")


class QcMaterialExceptionRow(Base):
    __tablename__ = "qc_material_exception"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_no: Mapped[str] = mapped_column(String, unique=True, index=True)
    receipt_id: Mapped[int] = mapped_column(Integer, index=True)
    discovered_at: Mapped[date] = mapped_column(Date, index=True)
    month_key: Mapped[str] = mapped_column(String, index=True)
    phenomenon: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="OPEN", index=True)
    handler: Mapped[str] = mapped_column(String, default="")
    handler_dept: Mapped[str] = mapped_column(String, default="")
    disposition: Mapped[str] = mapped_column(String, default="")
    disposition_detail: Mapped[str] = mapped_column(Text, default="")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_by: Mapped[str] = mapped_column(String, default="")
    close_result: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")


class QcExceptionEventRow(Base):
    __tablename__ = "qc_exception_event"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_id: Mapped[int] = mapped_column(Integer, index=True)
    from_status: Mapped[str] = mapped_column(String)
    to_status: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String, default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)


class QcDailyDefectRow(Base):
    __tablename__ = "qc_daily_defect"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month_key: Mapped[str] = mapped_column(String, index=True)
    record_date: Mapped[date] = mapped_column(Date, index=True)
    week_no: Mapped[int] = mapped_column(Integer)
    dept_found: Mapped[str] = mapped_column(String)
    shift: Mapped[str] = mapped_column(String, default="")
    item_code: Mapped[str | None] = mapped_column(String, nullable=True)
    model_no: Mapped[str] = mapped_column(String, default="")
    product_name: Mapped[str] = mapped_column(String)
    production_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    defect_qty: Mapped[int] = mapped_column(Integer, default=0)
    defect_category: Mapped[str] = mapped_column(String, default="")
    defect_specific: Mapped[str] = mapped_column(String, default="")
    defect_detail: Mapped[str] = mapped_column(Text, default="")
    handling_result: Mapped[str] = mapped_column(Text, default="")
    dept_responsible: Mapped[str] = mapped_column(String, default="")
    case_no: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")


class QcCustomerComplaintRow(Base):
    __tablename__ = "qc_customer_complaint"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month_key: Mapped[str] = mapped_column(String, index=True)
    record_date: Mapped[date] = mapped_column(Date, index=True)
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String)
    customer_project: Mapped[str] = mapped_column(String, default="")
    item_code: Mapped[str] = mapped_column(String, index=True)
    product_name: Mapped[str] = mapped_column(String)
    production_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String, default="")
    category_detail: Mapped[str] = mapped_column(String, default="")
    sample_sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sample_result: Mapped[str] = mapped_column(Text, default="")
    root_cause: Mapped[str] = mapped_column(Text, default="")
    corrective_action: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")


class QcExternalAuditRow(Base):
    __tablename__ = "qc_external_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String)
    audit_type: Mapped[str] = mapped_column(String)
    nc_count: Mapped[int] = mapped_column(Integer, default=0)
    audit_result: Mapped[str] = mapped_column(String)
    auditors: Mapped[str] = mapped_column(String)
    rectify_reply_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")


class QcLabExternalRequestRow(Base):
    __tablename__ = "qc_lab_external_request"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month_key: Mapped[str] = mapped_column(String, index=True)
    accepted_date: Mapped[date] = mapped_column(Date, index=True)
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_name: Mapped[str] = mapped_column(String)
    product_name: Mapped[str] = mapped_column(String)
    test_purpose: Mapped[str] = mapped_column(String, default="")
    test_items: Mapped[str] = mapped_column(Text, default="")
    request_dept: Mapped[str] = mapped_column(String, default="")
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")


class QcSwabPointRow(Base):
    __tablename__ = "qc_swab_point"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    point_code: Mapped[str] = mapped_column(String, index=True)
    point_name: Mapped[str] = mapped_column(String)
    detail_name: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class QcSwabTestRow(Base):
    __tablename__ = "qc_swab_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    point_id: Mapped[int] = mapped_column(Integer, index=True)
    month_key: Mapped[str] = mapped_column(String, index=True)
    experiment_date: Mapped[date] = mapped_column(Date, index=True)
    weekday: Mapped[str] = mapped_column(String, default="")
    week_no: Mapped[int] = mapped_column(Integer)
    sampling_date: Mapped[date] = mapped_column(Date, index=True)
    tpc_cfu_ml: Mapped[str] = mapped_column(String, default="")
    tpc_cfu_ml_raw: Mapped[str] = mapped_column(String, default="")
    coliform_cfu_ml: Mapped[str] = mapped_column(String, default="")
    coliform_cfu_ml_raw: Mapped[str] = mapped_column(String, default="")
    verdict_computed: Mapped[str] = mapped_column(String, default="MANUAL")
    verdict_final: Mapped[str | None] = mapped_column(String, nullable=True)
    override_reason: Mapped[str] = mapped_column(Text, default="")
    fail_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")


class QcProductTestRow(Base):
    __tablename__ = "qc_product_test"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    month_key: Mapped[str] = mapped_column(String, index=True)
    experiment_date: Mapped[date] = mapped_column(Date, index=True)
    weekday: Mapped[str] = mapped_column(String, default="")
    week_no: Mapped[int] = mapped_column(Integer)
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True)
    customer_name: Mapped[str] = mapped_column(String, default="")
    product_name: Mapped[str] = mapped_column(String)
    item_code: Mapped[str | None] = mapped_column(String, nullable=True)
    sampling_date: Mapped[date] = mapped_column(Date, index=True)
    moisture_pct: Mapped[str] = mapped_column(String, default="")
    moisture_pct_raw: Mapped[str] = mapped_column(String, default="")
    coliform_cfu_g: Mapped[str] = mapped_column(String, default="")
    coliform_cfu_g_raw: Mapped[str] = mapped_column(String, default="")
    tpc_cfu_g: Mapped[str] = mapped_column(String, default="")
    tpc_cfu_g_raw: Mapped[str] = mapped_column(String, default="")
    verdict_computed: Mapped[str] = mapped_column(String, default="MANUAL")
    verdict_final: Mapped[str | None] = mapped_column(String, nullable=True)
    override_reason: Mapped[str] = mapped_column(Text, default="")
    fail_reason: Mapped[str] = mapped_column(Text, default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String, default="")


class InvInboundDailyRow(Base):
    """仓库确认入库（成品/半成品），统计只读。"""

    __tablename__ = "inv_inbound_daily"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    schedule_dept: Mapped[str] = mapped_column(String, index=True)
    group_code: Mapped[str] = mapped_column(String, default="")
    item_code: Mapped[str] = mapped_column(String, index=True)
    qty_board: Mapped[int] = mapped_column(Integer)
    kg_per_board_snap: Mapped[str | None] = mapped_column(Numeric(18, 6), nullable=True)
    source: Mapped[str] = mapped_column(String, default="MOCK")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="")


class InvIssueRow(Base):
    """内部领用：INTERNAL / RD / SALES / QC。"""

    __tablename__ = "inv_issue"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    schedule_dept: Mapped[str] = mapped_column(String, default="FINISHED_DEPT")
    dest: Mapped[str] = mapped_column(String)
    item_code: Mapped[str] = mapped_column(String, index=True)
    qty_board: Mapped[int] = mapped_column(Integer)
    kg_per_board_snap: Mapped[str | None] = mapped_column(Numeric(18, 6), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String, default="")


class DeliveryProjectRow(Base):
    """大客户专项。进度在步骤表，不挂销售订单交期。"""

    __tablename__ = "delivery_project"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    customer_code: Mapped[str] = mapped_column(String, index=True)
    order_no: Mapped[str] = mapped_column(String, default="")


class DeliveryProjectStepRow(Base):
    """专项环节内的一步。大盘一格 = 同一 stage 的全部步骤都有发生日期。"""

    __tablename__ = "delivery_project_step"
    __table_args__ = (UniqueConstraint("project_code", "stage_code", "step_no"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String, index=True)
    stage_code: Mapped[str] = mapped_column(String)
    step_no: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str] = mapped_column(String)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


class CrmVisitRow(Base):
    """销售拜访。草稿不进时间线、有效拜访和分布。"""

    __tablename__ = "crm_visit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String, default="CONFIRMED")
    owner_sales: Mapped[str] = mapped_column(String, index=True)
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String, default="")
    visit_kind: Mapped[str] = mapped_column(String, default="现有客户")
    narrative: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(String, default="关系建联")
    next_step: Mapped[str] = mapped_column(String, default="")
    next_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    opportunity_name: Mapped[str] = mapped_column(String, default="")
    opportunity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_in_at: Mapped[datetime] = mapped_column(DateTime)
    check_out_at: Mapped[datetime] = mapped_column(DateTime)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False)
    location_note: Mapped[str] = mapped_column(String, default="")
    photo_note: Mapped[str] = mapped_column(String, default="")
    created_customer: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CrmSalesGoalRow(Base):
    """销售目标。完成数另算，不在这里记。"""

    __tablename__ = "crm_sales_goal"
    __table_args__ = (UniqueConstraint("owner_sales", "metric"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_sales: Mapped[str] = mapped_column(String, index=True)
    metric: Mapped[str] = mapped_column(String)
    target_qty: Mapped[int] = mapped_column(Integer, default=0)


class CrmSalesGoalPeriodRow(Base):
    """销售目标 · 年 / 月 / 周。"""

    __tablename__ = "crm_sales_goal_period"
    __table_args__ = (UniqueConstraint("owner_sales", "period_kind", "period_key", "metric"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_sales: Mapped[str] = mapped_column(String, index=True)
    owner_dept: Mapped[str] = mapped_column(String, default="销售部")
    period_kind: Mapped[str] = mapped_column(String)
    period_key: Mapped[str] = mapped_column(String)
    metric: Mapped[str] = mapped_column(String)
    target_qty: Mapped[int] = mapped_column(Integer, default=0)
    target_amount: Mapped[str] = mapped_column(Numeric(18, 2), default="0")
    created_by: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class CrmLeadRow(Base):
    __tablename__ = "crm_lead"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="待分配")
    contact_name: Mapped[str] = mapped_column(String)
    gender: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="", index=True)
    wechat: Mapped[str] = mapped_column(String, default="")
    company_name: Mapped[str] = mapped_column(String, default="")
    address_region: Mapped[str] = mapped_column(String, default="")
    address_detail: Mapped[str] = mapped_column(String, default="")
    annual_revenue: Mapped[str] = mapped_column(String, default="")
    industry: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String, default="")
    detail_text: Mapped[str] = mapped_column(Text, default="")
    customer_level: Mapped[str] = mapped_column(String, default="")
    tags: Mapped[str] = mapped_column(String, default="")
    convert_note: Mapped[str] = mapped_column(Text, default="")
    lost_reason: Mapped[str] = mapped_column(String, default="")
    owner_sales: Mapped[str] = mapped_column(String, default="", index=True)
    owner_dept: Mapped[str] = mapped_column(String, default="")
    pool_name: Mapped[str] = mapped_column(String, default="默认线索池")
    assigned_by: Mapped[str] = mapped_column(String, default="")
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class CrmLeadPoolRuleRow(Base):
    __tablename__ = "crm_lead_pool_rule"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_name: Mapped[str] = mapped_column(String, unique=True)
    admin_name: Mapped[str] = mapped_column(String)
    member_names_json: Mapped[str] = mapped_column(Text, default="[]")
    recycle_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class CrmFieldVisitRow(Base):
    """电脑端拜访签到 · 外勤单。"""

    __tablename__ = "crm_field_visit"
    code: Mapped[str] = mapped_column(String, primary_key=True)
    owner_sales: Mapped[str] = mapped_column(String, index=True)
    visit_plan: Mapped[str] = mapped_column(String, default="")
    title: Mapped[str] = mapped_column(String, default="")
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    customer_name: Mapped[str] = mapped_column(String, default="")
    visit_kind: Mapped[str] = mapped_column(String, default="老客户拜访")
    expected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expected_address: Mapped[str] = mapped_column(String, default="")
    before_note: Mapped[str] = mapped_column(Text, default="")
    situation_note: Mapped[str] = mapped_column(Text, default="")
    photo_note: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="待签到")
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_in_location: Mapped[str] = mapped_column(String, default="")
    check_out_location: Mapped[str] = mapped_column(String, default="")
    linked_visit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    progress_tags_json: Mapped[str] = mapped_column(Text, default="[]")
    meets_standard: Mapped[bool | None] = mapped_column(nullable=True)
    eval_source: Mapped[str] = mapped_column(String, default="")
    standard_reason: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class CrmFieldVisitLogRow(Base):
    """外勤拜访时间线条目。"""

    __tablename__ = "crm_field_visit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    visit_code: Mapped[str] = mapped_column(String, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime)
    body: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String, default="")


class CrmFollowRecordRow(Base):
    """跟进记录 · 线索 / 商机 / 客户共用。"""

    __tablename__ = "crm_follow_record"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_type: Mapped[str] = mapped_column(String, index=True)
    lead_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    customer_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    visit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follow_date: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text, default="")
    next_follow_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    owner_sales: Mapped[str] = mapped_column(String, default="")
    photo_note: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
