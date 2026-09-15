"""三单全局倒排（seed expected_results.all_orders_global）。"""

from datetime import date

from engine.schedule import schedule
from tests.helpers import semi_wo_of, tasks_of


def test_br25_global_three_orders_due_desc(input_builder, schedule_input):
    core = [o for o in schedule_input.orders if o.order_no in ("SO-001", "SO-002", "SO-003")]
    result = schedule(input_builder(core))
    assert len(core) == 3
    assert tasks_of(result, "P1") == [
        (date(2026, 9, 22), 120),
        (date(2026, 9, 23), 300),
    ]
    assert tasks_of(result, "P4") == [(date(2026, 9, 24), 312)]
    p2 = tasks_of(result, "P2")
    assert p2[0] == (date(2026, 9, 29), 36)
    assert len(p2) == 7
    semi = semi_wo_of(result, "SO-002")
    assert semi is not None
    assert semi.qty_board_plan == 282
    assert tasks_of(result, "S2") == [(date(2026, 9, 25), 282)]
