"""种子 fixture。today 固定 2026-09-15；测试 reserved_ratio = 0。"""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from engine.models import (
    CalendarDay,
    Group,
    Item,
    ItemRoute,
    Order,
    PriorityWeights,
    ScheduleConfig,
    ScheduleInput,
    SortMode,
    Sph,
    UomConvert,
)

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
                    group_code=group["code"],
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
    return ScheduleInput(
        today=today,
        orders=orders,
        items=items,
        uom=uom,
        routes=routes,
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
    return schedule_input.sph_of("S2", "SEMI")


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
