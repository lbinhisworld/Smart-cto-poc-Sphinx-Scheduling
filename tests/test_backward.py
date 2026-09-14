"""§11 T4 倒排基础（BR-20 ~ BR-24）。"""

from datetime import date
from decimal import Decimal

from engine.schedule import schedule

EPS = Decimal("0.0001")


def _tasks_of(result, item_code: str) -> list[tuple[date, int]]:
    wo_nos = {wo.wo_no for wo in result.wos if wo.item_code == item_code}
    rows = [(t.task_date, t.qty_board) for t in result.tasks if t.wo_no in wo_nos]
    return sorted(rows)


def test_br20_br24_backward_basic_so001(input_builder, so_001):
    result = schedule(input_builder([so_001]))
    assert _tasks_of(result, "P1") == [
        (date(2026, 9, 22), 120),
        (date(2026, 9, 23), 300),
    ]
    wo = result.wos[0]
    assert wo.plan_start == date(2026, 9, 22)
    assert wo.plan_end == date(2026, 9, 23)
    assert wo.due_date == so_001.due_date

    by_date = {t.task_date: t for t in result.tasks}
    t22 = by_date[date(2026, 9, 22)]
    t23 = by_date[date(2026, 9, 23)]
    assert abs(t22.hours_wall - Decimal("3.2")) < EPS
    assert abs(t23.hours_wall - Decimal("8")) < EPS
    assert abs(t23.hours_man - Decimal("24")) < EPS


def test_br21_br22_backward_skip_weekend_so003(input_builder, so_003):
    """SO-003 交期 9/24，齐套 9/20；312 版一天装下。"""
    result = schedule(input_builder([so_003]))
    assert _tasks_of(result, "P4") == [(date(2026, 9, 24), 312)]
    assert result.wos[0].due_date == so_003.due_date
    assert so_003.due_date == date(2026, 9, 24)
