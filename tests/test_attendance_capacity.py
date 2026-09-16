"""A 链路：出勤 → 排程产能（纯函数）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.attendance import effective_headcount, scaled_day_hours
from engine.models import CalendarDay, Dept, GroupCode


def _day(*, present: int | None = None) -> CalendarDay:
    return CalendarDay(
        dept=Dept.FINISHED_DEPT,
        group_code=GroupCode.MOLD,
        work_date=date(2026, 10, 1),
        is_workday=True,
        hours_per_day=Decimal("8"),
        headcount=4,
        headcount_present=present,
        reserved_ratio=Decimal("0"),
    )


def test_effective_headcount_uses_present_when_set():
    assert effective_headcount(_day(present=2)) == 2
    assert effective_headcount(_day(present=None)) == 4


def test_scaled_day_hours_proportional_to_attendance():
    full = scaled_day_hours(_day(present=None), Decimal("8"), scale=True)
    assert full == Decimal("8.0000")
    half = scaled_day_hours(_day(present=2), Decimal("8"), scale=True)
    assert half == Decimal("4.0000")


def test_scaled_day_hours_skipped_when_scale_off():
    assert scaled_day_hours(_day(present=1), Decimal("8"), scale=False) == Decimal("8")
