"""§11 T6 改交期演示（BR-33/35/47，BR-27 红线）。"""

from datetime import date

from engine.models import ConflictLv
from engine.schedule import schedule
from tests.helpers import earliest_finish_from_result, has_conflict, semi_wo_of


def test_br35_br47_semi_infeasible_e2_earliest(input_builder, so_002, order_with_due):
    order = order_with_due(so_002, date(2026, 9, 23))
    result = schedule(input_builder([order]))
    assert has_conflict(result, "E2", level=ConflictLv.RED)
    assert earliest_finish_from_result(result) == date(2026, 9, 29)
    assert order.due_date == date(2026, 9, 23)


def test_br33_semi_into_frozen_zone_no_e2(input_builder, so_002, order_with_due):
    order = order_with_due(so_002, date(2026, 9, 30))
    result = schedule(input_builder([order]))
    semi = semi_wo_of(result, "SO-002")
    assert semi is not None
    assert semi.plan_start == date(2026, 9, 18)
    assert has_conflict(result, "E2") is False
