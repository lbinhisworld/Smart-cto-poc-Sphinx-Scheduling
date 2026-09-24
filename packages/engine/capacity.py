"""组产能与工时（BR-10 ~ BR-14）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_DOWN
from typing import Sequence

from engine.models import (
    CalendarDay,
    CapacityOverride,
    Conflict,
    ConflictLv,
    Dept,
    GroupCode,
    Sph,
    SphBasis,
    UomConvert,
)
from engine.attendance import effective_headcount, scaled_day_hours
from engine.uom import sph_to_board_per_hour

HOURS_Q = Decimal("0.0001")


def _q4(value: Decimal) -> Decimal:
    return value.quantize(HOURS_Q)


def group_rate(sph: Sph, crew_plan: int, converts: Sequence[UomConvert]) -> Decimal:
    """组小时产能，单位：版/小时。

    BR-10 SINGLE：sph_board × crew_plan
    BR-11 CREW：sph_board（人数已含在 SPH 内，禁止再乘）
    """
    sph_board = sph_to_board_per_hour(sph.sph_value, sph.sph_uom, converts)
    if sph.sph_basis == SphBasis.SINGLE:
        return sph_board * Decimal(crew_plan)
    return sph_board


def detect_e8(sph: Sph, crew_plan: int) -> Conflict | None:
    """CREW 口径下 crew_plan ≠ sph_crew → E8（BR-11）。"""
    if sph.sph_basis != SphBasis.CREW:
        return None
    if sph.sph_crew is None or crew_plan == sph.sph_crew:
        return None
    return Conflict(
        code="E8",
        level=ConflictLv.YELLOW,
        message="投入人数与 SPH 标定不符，结果不可信",
        suggest="ADD_CREW",
    )


def hours_wall(qty_board: int, sph: Sph, crew_plan: int, converts: Sequence[UomConvert]) -> Decimal:
    """墙钟小时 = qty_board ÷ group_rate（BR-12）。"""
    rate = group_rate(sph, crew_plan, converts)
    return _q4(Decimal(qty_board) / rate)


def hours_man(wall: Decimal, crew_plan: int) -> Decimal:
    """人·时 = hours_wall × crew_plan（BR-12）。"""
    return _q4(wall * Decimal(crew_plan))


def calendar_day(
    calendar: Sequence[CalendarDay],
    dept: Dept,
    group_code: GroupCode,
    work_date: date,
) -> CalendarDay | None:
    for row in calendar:
        if row.dept == dept and row.group_code == group_code and row.work_date == work_date:
            return row
    return None


def is_workday(
    calendar: Sequence[CalendarDay],
    dept: Dept,
    group_code: GroupCode,
    work_date: date,
) -> bool:
    row = calendar_day(calendar, dept, group_code, work_date)
    return bool(row and row.is_workday)


def _override_hours(
    overrides: Sequence[CapacityOverride] | None,
    dept: Dept,
    group_code: GroupCode,
    work_date: date,
) -> Decimal | None:
    for row in overrides or ():
        if row.dept == dept and row.group_code == group_code and row.work_date == work_date:
            return row.hours_per_day
    return None


def calendar_hours(
    calendar: Sequence[CalendarDay],
    dept: Dept,
    group_code: GroupCode,
    work_date: date,
    overrides: Sequence[CapacityOverride] | None = None,
    *,
    attendance_scale: bool = False,
) -> Decimal:
    oh = _override_hours(overrides, dept, group_code, work_date)
    if oh is not None:
        return oh
    row = calendar_day(calendar, dept, group_code, work_date)
    if row is None:
        return Decimal(0)
    return scaled_day_hours(row, row.hours_per_day, scale=attendance_scale)


def sph_board_rate(sph: Sph, converts: Sequence[UomConvert]) -> Decimal:
    """单人（或 CREW 整组）小时产能，单位：版/小时。"""
    return sph_to_board_per_hour(sph.sph_value, sph.sph_uom, converts)


def person_day_hours(
    calendar: Sequence[CalendarDay],
    dept: Dept,
    group_code: GroupCode,
    work_date: date,
    reserved_ratio: Decimal,
    overrides: Sequence[CapacityOverride] | None = None,
) -> Decimal:
    """一个人当天可用墙钟。"""
    hours = calendar_hours(calendar, dept, group_code, work_date, overrides) * (
        Decimal(1) - reserved_ratio
    )
    return _q4(hours)


def available_person_hours(
    calendar: Sequence[CalendarDay],
    dept: Dept,
    group_code: GroupCode,
    work_date: date,
    reserved_ratio: Decimal,
    overrides: Sequence[CapacityOverride] | None = None,
) -> Decimal:
    """当天可用人·时 = 在编（有实到则用实到）× 一个人的可用工时。"""
    row = calendar_day(calendar, dept, group_code, work_date)
    if row is None:
        return Decimal(0)
    one = person_day_hours(
        calendar, dept, group_code, work_date, reserved_ratio, overrides
    )
    return _q4(one * Decimal(effective_headcount(row)))


def day_capacity(
    calendar: Sequence[CalendarDay],
    dept: Dept,
    group_code: GroupCode,
    work_date: date,
    sph: Sph,
    crew_plan: int,
    converts: Sequence[UomConvert],
    reserved_ratio: Decimal,
    overrides: Sequence[CapacityOverride] | None = None,
    crew_sets: int = 1,
) -> int:
    """组日容量（版），向下取整。

    单人口径：在编人数 × 有效工时 × 单人小时产能。`crew_plan` 不决定上限。
    多人配合：有效工时 × 标准小时产能 × 组套数。在编不乘进产量（BR-11）。
    """
    hours = person_day_hours(
        calendar, dept, group_code, work_date, reserved_ratio, overrides
    )
    sets = crew_sets if crew_sets > 0 else 1
    if sph.sph_basis == SphBasis.SINGLE:
        row = calendar_day(calendar, dept, group_code, work_date)
        head = effective_headcount(row) if row is not None else 0
        raw = hours * Decimal(head) * sph_board_rate(sph, converts)
    else:
        raw = hours * group_rate(sph, crew_plan, converts) * Decimal(sets)
    return int(raw.to_integral_value(rounding=ROUND_DOWN))
