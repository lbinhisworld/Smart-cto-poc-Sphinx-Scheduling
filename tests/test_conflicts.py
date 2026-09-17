"""§11 T9 冲突软约束（BR-50）。"""

from datetime import date

from engine.conflicts import due_conflict_suggest, e2_conflict_message
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


def test_due_suggest_feasible_when_fastest_not_after_due():
    assert due_conflict_suggest(date(2026, 9, 22), date(2026, 10, 8)) == "FEASIBLE:2026-09-22"
    assert due_conflict_suggest(date(2026, 9, 24), date(2026, 9, 22)) == "EARLIEST:2026-09-24"
    assert due_conflict_suggest(date(2026, 9, 22), date(2026, 9, 22)) == "FEASIBLE:2026-09-22"
    assert due_conflict_suggest(None, date(2026, 10, 8)) == "REVIEW_WINDOW"


def test_e2_message_feasible_does_not_imply_due_miss():
    msg = e2_conflict_message(
        "SO-S004",
        date(2026, 10, 8),
        date(2026, 9, 22),
        item_code="S6",
        gross=80,
        from_stock=0,
        net=80,
    )
    assert "缺口 80 版" in msg
    assert "必须开半成品工单" in msg
    assert "10/8" in msg
    assert "9/22" in msg
    assert "交期本身够" in msg
    assert "无法满足" not in msg


def test_e2_message_late_suggests_not_before_fastest():
    late = e2_conflict_message(
        "SO-004",
        date(2026, 9, 22),
        date(2026, 9, 24),
        item_code="S2",
        gross=412,
        from_stock=130,
        net=282,
    )
    assert "缺口 282 版" in late
    assert "必须开半成品工单" in late
    assert "无法满足 9/22 交付" in late
    assert "建议交付不早于 9/24" in late
