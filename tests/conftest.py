"""种子 fixture。today 固定 2026-09-15；测试 reserved_ratio = 0。"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from engine.models import (
    BomLine,
    CalendarDay,
    ComponentRole,
    Dept,
    Group,
    GroupCode,
    Item,
    ItemRoute,
    KitMode,
    Order,
    PriorityWeights,
    ScheduleConfig,
    ScheduleInput,
    SortMode,
    Sph,
    Uom,
    UomConvert,
    Wo,
    WoStatus,
    WoType,
)
from engine.schedule import schedule

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "seed" / "seed_data.json"
SCHEDULE_YAML = ROOT / "config" / "schedule.yaml"
WEIGHTS_YAML = ROOT / "config" / "weights.yaml"

TODAY = date(2026, 9, 15)


def load_seed() -> dict:
    with SEED_PATH.open(encoding="utf-8") as fh:
        return json.load(fh, parse_float=Decimal)


def load_schedule_config(*, reserved_ratio: Decimal | None = None) -> ScheduleConfig:
    with SCHEDULE_YAML.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    with WEIGHTS_YAML.open(encoding="utf-8") as fh:
        weights = yaml.safe_load(fh)
    if reserved_ratio is None:
        reserved_ratio = Decimal(str(raw["reserved_ratio"]))
    return ScheduleConfig(
        fence_days=raw["fence_days"],
        protocol_days=raw["protocol_days"],
        ripple_limit=raw["ripple_limit"],
        deadband_days=Decimal(str(raw["deadband_days"])),
        deadband_hours_ratio=Decimal(str(raw["deadband_hours_ratio"])),
        reserved_ratio=reserved_ratio,
        horizon_days=raw["horizon_days"],
        jit=raw["jit"],
        sort_mode=SortMode(raw["sort_mode"]),
        default_lead_time_days=raw["default_lead_time_days"],
        weights=PriorityWeights.model_validate(weights),
        kit_mode=KitMode(raw.get("kit_mode", "WARN")),
    )


def _expand_calendar(seed: dict, reserved_ratio: Decimal) -> list[CalendarDay]:
    cal = seed["calendar"]
    start = date.fromisoformat(cal["range"][0])
    end = date.fromisoformat(cal["range"][1])
    workdays = set(cal["workdays"])
    hours = Decimal(str(cal["hours_per_day"]))
    days: list[CalendarDay] = []
    cursor = start
    while cursor <= end:
        is_wd = cursor.isoweekday() in workdays
        for group in seed["groups"]:
            days.append(
                CalendarDay(
                    dept=Dept(group["dept"]),
                    group_code=GroupCode(group["code"]),
                    work_date=cursor,
                    is_workday=is_wd,
                    hours_per_day=hours,
                    headcount=group["headcount"],
                    reserved_ratio=reserved_ratio,
                )
            )
        cursor += timedelta(days=1)
    return days


def build_schedule_input(
    seed: dict,
    *,
    today: date = TODAY,
    reserved_ratio: Decimal = Decimal("0"),
    order_nos: list[str] | None = None,
) -> ScheduleInput:
    items = {row["item_code"]: Item.model_validate(row) for row in seed["items"]}
    uom: dict[str, list[UomConvert]] = {}
    for row in seed["uom_converts"]:
        conv = UomConvert.model_validate(row)
        uom.setdefault(conv.item_code, []).append(conv)
    routes = {row["item_code"]: ItemRoute.model_validate(row) for row in seed["routes"]}
    sph = {
        (row["item_code"], row["group_code"]): Sph.model_validate(row) for row in seed["sph"]
    }
    orders = [Order.model_validate(row) for row in seed["orders"]]
    if order_nos is not None:
        wanted = set(order_nos)
        orders = [o for o in orders if o.order_no in wanted]
    stock = {k: Decimal(str(v)) for k, v in seed["stock"].items()}
    bom_lines: dict[str, list[BomLine]] = {}
    for row in seed.get("bom_lines", []):
        bl = BomLine(
            parent_item_code=row["parent_item_code"],
            line_no=row["line_no"],
            component_item_code=row["component_item_code"],
            component_role=ComponentRole(row["component_role"]),
            qty_per_parent=Decimal(str(row["qty_per_parent"])),
            qty_basis_uom=Uom(row.get("qty_basis_uom", "BOX")),
            scrap_rate=Decimal(str(row["scrap_rate"])) if row.get("scrap_rate") is not None else None,
            offset_days=row.get("offset_days", 0),
            lead_time_days=row.get("lead_time_days", 4),
            kit_critical=row.get("kit_critical", True),
        )
        bom_lines.setdefault(bl.parent_item_code, []).append(bl)
    return ScheduleInput(
        today=today,
        orders=orders,
        items=items,
        uom=uom,
        routes=routes,
        bom_lines=bom_lines,
        sph=sph,
        calendar=_expand_calendar(seed, reserved_ratio),
        stock=stock,
        locked_tasks=[],
        config=load_schedule_config(reserved_ratio=reserved_ratio),
    )


@pytest.fixture(scope="session")
def today() -> date:
    return TODAY


@pytest.fixture(scope="session")
def seed_raw() -> dict:
    return load_seed()


@pytest.fixture(scope="session")
def groups(seed_raw: dict) -> list[Group]:
    return [Group.model_validate(row) for row in seed_raw["groups"]]


@pytest.fixture
def schedule_input(seed_raw: dict, today: date) -> ScheduleInput:
    return build_schedule_input(seed_raw, today=today, reserved_ratio=Decimal("0"))


@pytest.fixture
def items(schedule_input: ScheduleInput):
    return schedule_input.items


@pytest.fixture
def p1(items):
    return items["P1"]


@pytest.fixture
def p2(items):
    return items["P2"]


@pytest.fixture
def s2(items):
    return items["S2"]


@pytest.fixture
def p4(items):
    return items["P4"]


@pytest.fixture
def p1_converts(schedule_input: ScheduleInput):
    return schedule_input.converts_for("P1")


@pytest.fixture
def p2_converts(schedule_input: ScheduleInput):
    return schedule_input.converts_for("P2")


@pytest.fixture
def s2_converts(schedule_input: ScheduleInput):
    return schedule_input.converts_for("S2")


@pytest.fixture
def p4_converts(schedule_input: ScheduleInput):
    return schedule_input.converts_for("P4")


@pytest.fixture
def p1_sph(schedule_input: ScheduleInput):
    return schedule_input.sph_of("P1", "MANUAL")


@pytest.fixture
def s2_sph(schedule_input: ScheduleInput):
    return schedule_input.sph_of("S2", "MOLD")


@pytest.fixture
def p4_sph(schedule_input: ScheduleInput):
    return schedule_input.sph_of("P4", "POURING")


@pytest.fixture
def so_001(schedule_input: ScheduleInput) -> Order:
    return next(o for o in schedule_input.orders if o.order_no == "SO-001")


@pytest.fixture
def so_002(schedule_input: ScheduleInput) -> Order:
    return next(o for o in schedule_input.orders if o.order_no == "SO-002")


@pytest.fixture
def so_003(schedule_input: ScheduleInput) -> Order:
    return next(o for o in schedule_input.orders if o.order_no == "SO-003")


@pytest.fixture
def input_builder(schedule_input: ScheduleInput):
    def _build(
        orders: list[Order] | None = None,
        *,
        stock: dict[str, Decimal] | None = None,
    ) -> ScheduleInput:
        updates: dict = {}
        if orders is not None:
            updates["orders"] = list(orders)
        if stock is not None:
            updates["stock"] = stock
        return schedule_input.model_copy(update=updates)

    return _build


@pytest.fixture
def order_with_due():
    def _patch(order: Order, due: date) -> Order:
        return order.model_copy(update={"due_date": due})

    return _patch


def _ripple_items_and_sph(schedule_input: ScheduleInput) -> ScheduleInput:
    """§13 涟漪算例：品项 A/C/E 共用 P1 手工组 SPH。"""
    p1 = schedule_input.items["P1"]
    items = dict(schedule_input.items)
    uom = dict(schedule_input.uom)
    sph = dict(schedule_input.sph)
    for code in ("A", "C", "E"):
        items[code] = p1.model_copy(update={"item_code": code, "item_name": f"ripple-{code}"})
        uom[code] = list(schedule_input.converts_for("P1"))
        sph[(code, GroupCode.MANUAL.value)] = schedule_input.sph_of("P1", "MANUAL")
    return schedule_input.model_copy(update={"items": items, "uom": uom, "sph": sph, "orders": []})


@pytest.fixture
def ripple_input(schedule_input: ScheduleInput) -> ScheduleInput:
    return _ripple_items_and_sph(schedule_input)


@pytest.fixture
def ripple_wos(today):
    def _build(*, qty_a: int = 300, qty_c: int = 300, qty_e: int = 300) -> list[Wo]:
        def _one(code: str, due: date, qty: int) -> Wo:
            return Wo(
                wo_no=code,
                wo_type=WoType.FINISHED,
                source_order_no=code,
                item_code=code,
                group_code=GroupCode.MANUAL,
                dept=Dept.FINISHED_DEPT,
                qty_order=Decimal(qty),
                qty_board_plan=qty,
                due_date=due,
                earliest_start=today,
                crew_plan=3,
                status=WoStatus.DRAFT,
            )

        return [
            _one("E", date(2026, 9, 21), qty_e),
            _one("C", date(2026, 9, 22), qty_c),
            _one("A", date(2026, 9, 23), qty_a),
        ]

    return _build


@pytest.fixture
def run_ripple(ripple_input: ScheduleInput):
    def _run(
        wos: list[Wo],
        *,
        sort_mode: SortMode = SortMode.DUE_DESC,
        pinned: list[str] | None = None,
        baseline=None,
        deadband_trigger: list[str] | None = None,
    ):
        cfg = ripple_input.config.model_copy(
            update={
                "sort_mode": sort_mode,
                "pinned_wo_nos": pinned or [],
            }
        )
        return schedule(
            ripple_input.model_copy(
                update={
                    "finished_override": wos,
                    "config": cfg,
                    "baseline": baseline,
                    "deadband_trigger_wo_nos": deadband_trigger or [],
                }
            )
        )

    return _run
