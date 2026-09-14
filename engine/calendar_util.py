"""工作日历辅助（纯函数，today 由入参传入）。"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Sequence

from engine.capacity import day_capacity, is_workday
from engine.models import CalendarDay, GroupCode, ScheduleInput, Sph, UomConvert, Wo


def add_natural_days(start: date, days: int) -> date:
    return start + timedelta(days=days)


def next_workday(calendar: Sequence[CalendarDay], group_code: GroupCode, start: date) -> date:
    cursor = start
    for _ in range(366):
        if is_workday(calendar, group_code, cursor):
            return cursor
        cursor += timedelta(days=1)
    return start


def count_workdays_forward(
    calendar: Sequence[CalendarDay],
    group_code: GroupCode,
    start: date,
    boards: int,
    sph: Sph,
    crew_plan: int,
    converts: Sequence[UomConvert],
    reserved_ratio: Decimal,
) -> tuple[date, date]:
    """从 start 起正排，返回 (plan_start, plan_end)。"""
    remaining = boards
    cursor = next_workday(calendar, group_code, start)
    plan_start: date | None = None
    plan_end: date | None = None
    guard = 0
    while remaining > 0:
        guard += 1
        if guard > 365:
            break
        if not is_workday(calendar, group_code, cursor):
            cursor += timedelta(days=1)
            continue
        cap = day_capacity(
            calendar, group_code, cursor, sph, crew_plan, converts, reserved_ratio
        )
        if cap <= 0:
            cursor += timedelta(days=1)
            continue
        qty = min(remaining, cap)
        if plan_start is None:
            plan_start = cursor
        plan_end = cursor
        remaining -= qty
        if remaining <= 0:
            break
        cursor += timedelta(days=1)
    if plan_start is None or plan_end is None:
        return start, start
    return plan_start, plan_end


def boards_workdays_needed(
    boards: int,
    day_cap: int,
) -> int:
    if day_cap <= 0:
        return 365
    return int(
        (Decimal(boards) / Decimal(day_cap)).to_integral_value(rounding=ROUND_CEILING)
    )
