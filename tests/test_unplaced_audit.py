"""E1 未安置过程必须可二次审计：逐日尝试 + 剩余 + 结论。"""

from datetime import date

from engine.schedule import schedule
from engine.trace import unplaced_audit_message


def test_unplaced_audit_message_lists_day_attempts():
    text = unplaced_audit_message(
        order_no="SO-S001",
        item_code="S2",
        due_date=date(2026, 10, 7),
        earliest_start=date(2026, 9, 15),
        remaining=42,
        attempts=[
            {"date": date(2026, 10, 6), "kind": "place", "qty": 80, "cap": 120, "occupied": 40},
            {"date": date(2026, 10, 3), "kind": "place", "qty": 80, "cap": 120, "occupied": 0},
            {"date": date(2026, 10, 2), "kind": "skip", "reason": "REST"},
            {"date": date(2026, 9, 30), "kind": "skip", "reason": "FULL", "cap": 120},
        ],
    )
    assert "从交期 10/7 往回填" in text
    assert "安排尝试" in text
    assert "10/6 放下 80 版" in text
    assert "10/2 非工作日跳过" in text
    assert "9/30 产能已满跳过" in text
    assert "碰到最早可排日 9/15，还剩 42 版" in text
    assert "所以结论：未能在最早可排日前安置完（E1）" in text


def test_tight_due_unplaced_event_has_audit_trail(input_builder, so_001):
    tight = so_001.model_copy(update={"due_date": date(2026, 9, 15)})
    result = schedule(input_builder([tight]))
    unps = [e for e in result.trace.events if e.kind == "unplaced"]
    assert unps
    msg = unps[0].message
    assert "安排尝试" in msg
    assert "放下" in msg
    assert "还剩" in msg and "版" in msg
    assert "所以结论" in msg
    assert unps[0].due_date == date(2026, 9, 15)
