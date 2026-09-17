"""M9 日期派生字段（BR-QC-04）。"""

from __future__ import annotations

from datetime import date

_WEEKDAY_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def week_no_iso(d: date) -> int:
    return int(d.isocalendar()[1])


def weekday_zh(d: date) -> str:
    return _WEEKDAY_ZH[d.weekday()]


def period_fields(d: date) -> dict:
    return {
        "month_key": month_key(d),
        "week_no": week_no_iso(d),
        "weekday": weekday_zh(d),
    }
