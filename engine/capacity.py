"""组产能与工时（BR-10 ~ BR-14）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_DOWN
from typing import Sequence

from engine.models import (
    CalendarDay,
    Conflict,
    ConflictLv,
    GroupCode,
    Sph,
    SphBasis,
    UomConvert,
)
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
    group_code: GroupCode,
    work_date: date,
) -> CalendarDay | None:
    for row in calendar:
        if row.group_code == group_code and row.work_date == work_date:
            return row
    return None


def is_workday(calendar: Sequence[CalendarDay], group_code: GroupCode, work_date: date) -> bool:
    row = calendar_day(calendar, group_code, work_date)
    return bool(row and row.is_workday)


def calendar_hours(calendar: Sequence[CalendarDay], group_code: GroupCode, work_date: date) -> Decimal:
    row = calendar_day(calendar, group_code, work_date)
    if row is None:
        return Decimal(0)
    return row.hours_per_day


def day_capacity(
    calendar: Sequence[CalendarDay],
    group_code: GroupCode,
    work_date: date,
    sph: Sph,
    crew_plan: int,
    converts: Sequence[UomConvert],
    reserved_ratio: Decimal,
) -> int:
    """组日容量（版），向下取整（BR-13）。

    有效工时 = hours_per_day × (1 − reserved_ratio)
    """
    hours = calendar_hours(calendar, group_code, work_date) * (Decimal(1) - reserved_ratio)
    raw = hours * group_rate(sph, crew_plan, converts)
    return int(raw.to_integral_value(rounding=ROUND_DOWN))
