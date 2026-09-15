from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    data: dict | list | None = None
    message: str = ""


class ScheduleBody(BaseModel):
    order_nos: list[str] = Field(default_factory=lambda: ["SO-001", "SO-002", "SO-003"])
    today: date
    reserved_ratio: float | None = 0.0


class OrderDuePatch(BaseModel):
    due_date: date


class SchedulingPoolBody(BaseModel):
    order_nos: list[str]
    action: str = "add"  # add | remove


class PublishPoolBody(BaseModel):
    today: date
    order_nos: list[str] | None = None
    reserved_ratio: float | None = 0.0
    force_red: bool = False


class OrderCreate(BaseModel):
    order_no: str
    customer: str
    sales_name: str = ""
    item_code: str
    qty_order: float
    unit: str = "BOX"
    due_date: date
    ready_date: date | None = None
    customer_level: int = 3
    amount: float = 0
    is_urgent: bool = True


class InsertTrialBody(BaseModel):
    order_no: str
    today: date
    reason: str = "客户催单"
    reserved_ratio: float | None = 0.0


class InsertApplyBody(InsertTrialBody):
    strategy: str = "B"
    requester: str = "demo"


class InteractivePreviewBody(BaseModel):
    today: date
    order_nos: list[str]
    baseline_wos: list[dict]
    baseline_tasks: list[dict]
    proposed_wos: list[dict]
    proposed_tasks: list[dict]
    trigger_task_id: int | None = None
    reserved_ratio: float | None = 0.0


class StockPatchBody(BaseModel):
    qty_available: float


class CellDetailBody(BaseModel):
    today: date
    dept: str = "FINISHED_DEPT"
    group_code: str
    task_date: date
    focus_task_id: int | None = None
    plan_version: int | None = None
    reserved_ratio: float | None = 0.0
    tasks: list[dict] | None = None
    result: dict | None = None
