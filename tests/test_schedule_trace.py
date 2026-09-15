"""倒排讲解 trace（落位旁白 + 占用账）。"""

from datetime import date

from engine.models import TraceAct
from engine.schedule import schedule


def _order(schedule_input, order_no: str):
    return next(o for o in schedule_input.orders if o.order_no == order_no)


def test_trace_queue_is_due_desc(input_builder, schedule_input):
    core = [o for o in schedule_input.orders if o.order_no in ("SO-001", "SO-002", "SO-003")]
    result = schedule(input_builder(core))
    assert result.trace is not None
    assert result.trace.sort_mode == "DUE_DESC"
    queue = [
        e
        for e in result.trace.events
        if e.kind == "queue_rank" and e.wo_type == "FINISHED"
    ]
    assert [e.order_no for e in queue] == ["SO-002", "SO-003", "SO-001"]
    assert [e.rank for e in queue] == [1, 2, 3]


def test_trace_place_so001_backward_occupancy(input_builder, schedule_input):
    so001 = _order(schedule_input, "SO-001")
    result = schedule(input_builder([so001]))
    places = [e for e in result.trace.events if e.kind == "place" and e.wo_type == "FINISHED"]
    assert places[0].task_date == date(2026, 9, 23)
    assert places[0].qty_board == 300
    assert places[0].remaining_after == 120
    assert places[0].free_before is not None and places[0].free_before >= 300
    assert places[1].task_date == date(2026, 9, 22)
    assert places[1].qty_board == 120
    assert places[1].remaining_after == 0
    assert all(e.act == TraceAct.PLACE for e in places)


def test_trace_has_five_acts_and_semi(input_builder, schedule_input):
    so002 = _order(schedule_input, "SO-002")
    result = schedule(input_builder([so002]))
    acts = {e.act for e in result.trace.events}
    assert TraceAct.EXPAND in acts
    assert TraceAct.QUEUE in acts
    assert TraceAct.PLACE in acts
    assert TraceAct.SEMI in acts
    assert TraceAct.CHECK in acts
    semi_exp = [e for e in result.trace.events if e.kind == "expand_semi"]
    assert semi_exp
    assert semi_exp[0].qty_board == 282
    check = next(e for e in result.trace.events if e.kind == "check_summary")
    assert "红" in check.message or "冲突" in check.message
