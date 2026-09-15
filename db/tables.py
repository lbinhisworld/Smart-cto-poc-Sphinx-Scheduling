"""SQLAlchemy 表映射（字段对齐 engine.models / 需求 §5）。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text
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
