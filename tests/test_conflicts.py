"""§11 T9 冲突软约束（BR-50）。"""

from datetime import date

from engine.models import WoStatus
from engine.schedule import schedule
from tests.helpers import finished_wo_of


def test_br50_conflicts_never_block_scheduling(input_builder, so_002, order_with_due):
    order = order_with_due(so_002, date(2026, 9, 23))
    result = schedule(input_builder([order]))
    finished = finished_wo_of(result, "SO-002")
    assert finished is not None
    assert finished.status == WoStatus.PLANNED
    assert result.conflicts
    assert result.conflicts[0].suggest is not None
