"""§11 T5 半成品两层（BR-30~36）。"""

from datetime import date
from decimal import Decimal

from engine.schedule import schedule
from tests.helpers import semi_wo_of, tasks_of


def test_br30_br36_semi_net_demand(input_builder, so_002):
    result = schedule(input_builder([so_002]))
    semi = semi_wo_of(result, "SO-002")
    assert semi is not None
    assert semi.qty_board_plan == 282
    assert semi.due_date == date(2026, 9, 25)
    p2_tasks = tasks_of(result, "P2")
    assert p2_tasks[0] == (date(2026, 9, 29), 36)
    assert len(p2_tasks) == 7
    assert result.dependencies
    assert result.dependencies[0].offset_days == 4
    assert result.dependencies[0].pred_wo_no == semi.wo_no
    assert result.dependencies[0].succ_wo_no.startswith("WO-SO-002")


def test_br32_semi_skipped_when_stock_enough(input_builder, so_002):
    result = schedule(input_builder([so_002], stock={"S2": Decimal("500")}))
    assert semi_wo_of(result, "SO-002") is None
