"""Pydantic 模型 —— 数据模型唯一事实源（需求 §5）。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Dept(str, Enum):
    FINISHED_DEPT = "FINISHED_DEPT"
    SEMI_DEPT = "SEMI_DEPT"


class GroupCode(str, Enum):
    MANUAL = "MANUAL"
    MOLD = "MOLD"
    POURING = "POURING"
    SEMI = "SEMI"


class WoType(str, Enum):
    FINISHED = "FINISHED"
    SEMI = "SEMI"


class WoStatus(str, Enum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    RELEASED = "RELEASED"
    DONE = "DONE"


class Uom(str, Enum):
    PCS = "PCS"
    BOARD = "BOARD"
    BOX = "BOX"
    PACK = "PACK"
    BAG = "BAG"
    CARTON = "CARTON"


class SphBasis(str, Enum):
    SINGLE = "SINGLE"
    CREW = "CREW"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MID = "MID"
    LOW = "LOW"


class ConflictLv(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREY = "GREY"
    BLUE = "BLUE"


class ChangeType(str, Enum):
    ADD = "ADD"
    MOVE = "MOVE"
    DELAY = "DELAY"
    LATE = "LATE"
    REMOVE = "REMOVE"


class SortMode(str, Enum):
    DUE_DESC = "DUE_DESC"
    PIN_FIRST = "PIN_FIRST"
    DUE_ASC = "DUE_ASC"


class InsertReason(str, Enum):
    CUSTOMER_RUSH = "客户催单"
    QUALITY_REWORK = "质量返工"
    SALES_MISS = "销售漏单"
    PLAN_MISTAKE = "计划失误"
    OTHER = "其他"


class InsertStrategy(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class PlanTrigger(str, Enum):
    INITIAL = "初始排产"
    CHANGE = "改单"
    INSERT = "插单"
    SCHEDULED = "定时重排"


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Item(_Model):
    """md_item 品项。"""

    item_code: str
    item_name: str
    dept: Dept
    group_code: GroupCode
    unit_sale: Uom
    pcs_per_board: int
    board_per_box: Decimal
    loss_rate: Decimal
    color: str
    is_semi: bool
    computable: bool


class UomConvert(_Model):
    """md_uom_convert：相邻两级，1 from_uom = factor × to_uom。"""

    item_code: str
    from_uom: Uom
    to_uom: Uom
    factor: Decimal


class ItemRoute(_Model):
    """md_item_route 工艺路线。"""

    item_code: str
    needs_semi: bool
    semi_item_code: str | None = None
    semi_board_per_box: Decimal | None = None
    lead_time_days: int = 4
    changeover_min: int = 30


class Sph(_Model):
    """md_sph SPH 四元组。"""

    item_code: str
    group_code: GroupCode
    sph_value: Decimal
    sph_basis: SphBasis
    sph_crew: int | None = None
    sph_uom: Uom
    crew_std: int
    confidence: Confidence
    effective_date: date
    source: str
    updated_by: str | None = None
    updated_at: datetime | None = None


class CalendarDay(_Model):
    """md_capacity_calendar 组日历一行。"""

    group_code: GroupCode
    work_date: date
    is_workday: bool
    hours_per_day: Decimal
    headcount: int
    reserved_ratio: Decimal = Decimal("0.15")


class Group(_Model):
    code: GroupCode
    name: str
    dept: Dept
    headcount: int
    hours_per_day: Decimal


class Order(_Model):
    """so_order。due_date 是锚，引擎禁止写回（BR-27）。"""

    order_no: str
    customer: str
    item_code: str
    qty_order: Decimal
    unit: Uom
    due_date: date
    ready_date: date | None = None
    customer_level: int = Field(ge=1, le=5)
    amount: Decimal = Decimal("0")
    is_urgent: bool = False


class Wo(_Model):
    wo_no: str
    wo_type: WoType
    source_order_no: str
    item_code: str
    group_code: GroupCode
    dept: Dept
    qty_order: Decimal
    qty_board_plan: int
    due_date: date
    plan_start: date | None = None
    plan_end: date | None = None
    earliest_start: date
    crew_plan: int
    status: WoStatus = WoStatus.DRAFT
    is_locked: bool = False
    override_reason: str | None = None
    plan_version: int = 0
    parent_wo_no: str | None = None
    priority_score: Decimal = Decimal("0")


class WoTask(_Model):
    task_id: int
    wo_no: str
    group_code: GroupCode
    task_date: date
    qty_board: int
    hours_wall: Decimal
    hours_man: Decimal
    crew_plan: int
    seq: int = 1
    changeover_min: int = 0
    qty_actual: int | None = None
    hours_actual: Decimal | None = None
    plan_version: int = 0


class WoDependency(_Model):
    pred_wo_no: str
    succ_wo_no: str
    dep_type: str = "FS"
    offset_days: int = 4


class WoInsertLog(_Model):
    wo_no: str
    requester: str
    requested_at: datetime
    reason: InsertReason
    strategy: InsertStrategy | None = None
    cost_json: dict[str, Any] = Field(default_factory=dict)
    approver: str | None = None
    plan_version_before: int | None = None
    plan_version_after: int | None = None


class PlanVersion(_Model):
    version_no: int
    created_at: datetime
    trigger: PlanTrigger
    snapshot_hash: str


class Conflict(_Model):
    code: str
    level: ConflictLv
    wo_no: str | None = None
    task_id: int | None = None
    message: str
    suggest: str | None = None


class Unplaced(_Model):
    wo_no: str
    code: str
    remaining: int
    reason: str
    earliest_finish: date | None = None


class PriorityWeights(_Model):
    urgency: Decimal = Decimal("0.5")
    customer_level: Decimal = Decimal("0.2")
    amount: Decimal = Decimal("0.1")
    ready: Decimal = Decimal("0.2")
    strategic: Decimal = Decimal("0.0")


class ScheduleConfig(_Model):
    fence_days: int = 4
    protocol_days: int = 10
    ripple_limit: int = 10
    deadband_days: Decimal = Decimal("0.5")
    deadband_hours_ratio: Decimal = Decimal("0.10")
    reserved_ratio: Decimal = Decimal("0.15")
    horizon_days: int = 21
    jit: bool = True
    sort_mode: SortMode = SortMode.DUE_DESC
    default_lead_time_days: int = 4
    weights: PriorityWeights = Field(default_factory=PriorityWeights)
    pinned_wo_nos: list[str] = Field(default_factory=list)


class ScheduleInput(_Model):
    today: date
    orders: list[Order]
    items: dict[str, Item]
    uom: dict[str, list[UomConvert]]
    routes: dict[str, ItemRoute]
    sph: dict[tuple[str, str], Sph]
    calendar: list[CalendarDay]
    stock: dict[str, Decimal]
    locked_tasks: list[WoTask] = Field(default_factory=list)
    config: ScheduleConfig

    def converts_for(self, item_code: str) -> list[UomConvert]:
        return self.uom.get(item_code, [])

    def sph_of(self, item_code: str, group_code: GroupCode | str) -> Sph:
        key = (item_code, group_code.value if isinstance(group_code, GroupCode) else group_code)
        return self.sph[key]


class ScheduleResult(_Model):
    wos: list[Wo] = Field(default_factory=list)
    tasks: list[WoTask] = Field(default_factory=list)
    dependencies: list[WoDependency] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    unplaced: list[Unplaced] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
