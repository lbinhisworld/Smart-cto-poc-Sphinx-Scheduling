"""工作中心 = 部门 × 工艺组（BR-组-01）。"""

from __future__ import annotations

from datetime import date

from engine.models import Dept, GroupCode


def wc_key(dept: Dept, group_code: GroupCode, work_date: date) -> tuple[str, str, date]:
    return (dept.value, group_code.value, work_date)


def wc_key_from_task(dept: Dept, group_code: GroupCode, work_date: date) -> tuple[str, str, date]:
    return wc_key(dept, group_code, work_date)
