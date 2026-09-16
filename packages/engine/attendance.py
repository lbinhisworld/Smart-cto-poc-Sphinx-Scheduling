"""出勤与日历在编合并（纯函数，供产能与人手校验）。"""

from __future__ import annotations

from decimal import Decimal

from engine.models import CalendarDay

_HOURS_Q = Decimal("0.0001")


def effective_headcount(day: CalendarDay) -> int:
    """实到优先，否则日历在编。"""
    if day.headcount_present is not None:
        return max(0, day.headcount_present)
    return day.headcount


def scaled_day_hours(
    day: CalendarDay,
    base_hours: Decimal,
    *,
    scale: bool,
) -> Decimal:
    """按实到/在编比例缩放日可用墙钟（POC：线性缩放）。"""
    if not scale or day.headcount_present is None or day.headcount <= 0:
        return base_hours
    ratio = Decimal(day.headcount_present) / Decimal(day.headcount)
    return (base_hours * ratio).quantize(_HOURS_Q)
