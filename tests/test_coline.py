"""同组同日同品项共线：点数、版数、并线决策文案。"""

from datetime import date
from decimal import Decimal

from engine.coline import (
    coline_conflicts,
    coline_decision_message,
    coline_summary_message,
    detect_coline,
    emit_sku_intersect_events,
    sku_share_message,
)
from engine.models import (
    Dept,
    GroupCode,
    ScheduleResult,
    TraceEvent,
    Wo,
    WoStatus,
    WoTask,
    WoType,
)


def _wo(no: str, order: str, item: str, *, wo_type: WoType = WoType.FINISHED) -> Wo:
    return Wo(
        wo_no=no,
        wo_type=wo_type,
        source_order_no=order,
        item_code=item,
        group_code=GroupCode.MANUAL if item.startswith("P") else GroupCode.MOLD,
        dept=Dept.FINISHED_DEPT if wo_type == WoType.FINISHED else Dept.SEMI_DEPT,
        qty_order=Decimal("20"),
        qty_board_plan=20,
        due_date=date(2026, 10, 8),
        earliest_start=date(2026, 9, 15),
        crew_plan=3,
        status=WoStatus.PLANNED,
    )


def _task(tid: int, wo_no: str, qty: int, day: date = date(2026, 9, 21)) -> WoTask:
    return WoTask(
        task_id=tid,
        wo_no=wo_no,
        dept=Dept.FINISHED_DEPT,
        group_code=GroupCode.MANUAL,
        task_date=day,
        qty_board=qty,
        hours_wall=Decimal("2"),
        hours_man=Decimal("6"),
        crew_plan=3,
    )


def test_detect_coline_same_item_same_cell():
    result = ScheduleResult(
        wos=[_wo("WO-A", "SO-A#L1", "P1"), _wo("WO-B", "SO-B#L1", "P1")],
        tasks=[_task(1, "WO-A", 20), _task(2, "WO-B", 30)],
    )
    groups, summary = detect_coline(result)
    assert len(groups) == 1
    assert summary.point_count == 1
    assert summary.qty_board_total == 50
    assert summary.order_count == 2
    assert summary.sku_count == 1
    assert groups[0].order_nos == ["SO-A", "SO-B"]
    blues = coline_conflicts(groups)
    assert blues and blues[0].code == "E7" and blues[0].level.value == "BLUE"


def test_detect_coline_different_items_same_cell():
    result = ScheduleResult(
        wos=[_wo("WO-A", "SO-A#L1", "P1"), _wo("WO-B", "SO-B#L1", "P4")],
        tasks=[_task(1, "WO-A", 20), _task(2, "WO-B", 20)],
    )
    groups, summary = detect_coline(result)
    assert groups == []
    assert summary.point_count == 0
    assert summary.qty_board_total == 0


def test_coline_decision_and_summary_copy():
    result = ScheduleResult(
        wos=[_wo("WO-A", "SO-A#L1", "P1"), _wo("WO-B", "SO-B#L1", "P1")],
        tasks=[_task(1, "WO-A", 20), _task(2, "WO-B", 20)],
    )
    groups, summary = detect_coline(result)
    text = coline_decision_message(groups[0])
    assert "并线决策" in text
    assert "SO-A" in text and "SO-B" in text
    assert "不并 WO" in text
    assert "本点并线 2 单 · 40 版" in text
    wrap = coline_summary_message(summary)
    assert "1 个点" in wrap
    assert "40 版" in wrap


def test_sku_intersect_event_for_shared_core():
    events: list[TraceEvent] = []
    wos = [
        _wo("WO-1", "SO-S001#L1", "P1"),
        _wo("WO-2", "SO-S001#L2", "P2"),
        _wo("WO-3", "SO-S002#L1", "P1"),
        _wo("WO-4", "SO-S002#L2", "P2"),
    ]
    emit_sku_intersect_events(events, wos)
    kinds = [e.kind for e in events]
    assert "expand_lines" in kinds
    assert "sku_intersect" in kinds
    inter = next(e for e in events if e.kind == "sku_intersect")
    assert "P1" in inter.message and "P2" in inter.message
    assert "SO-S001" in inter.message and "SO-S002" in inter.message
    assert "∩" not in inter.message
    assert "核心相交" not in inter.message
    assert "同一组货" in inter.message
    expand = next(e for e in events if e.kind == "expand_lines")
    assert "这张单要做" in expand.message


def test_sku_share_message_truncates_long_order_list():
    orders = [f"SO-S{i:03d}" for i in range(1, 16)]
    text = sku_share_message(["P1M"], orders)
    assert "15 张订单都要做 P1M" in text
    assert "等共 15 张" in text
    assert "∩" not in text
