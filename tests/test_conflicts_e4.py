"""E4 冲突含墙钟合计/上限/超限数值。"""

from datetime import date
from decimal import Decimal

from engine.conflicts import detect_conflicts
from engine.models import (
    ConflictLv,
    Dept,
    GroupCode,
    ScheduleInput,
    ScheduleResult,
    WoTask,
)


def test_e4_includes_hours_breakdown(schedule_input: ScheduleInput):
    inp = schedule_input
    d = date(2026, 10, 1)
    task = WoTask(
        task_id=1,
        wo_no="WO-1",
        dept=Dept.FINISHED_DEPT,
        group_code=GroupCode.MOLD,
        task_date=d,
        qty_board=100,
        hours_wall=Decimal("12"),
        hours_man=Decimal("12"),
        crew_plan=1,
    )
    result = ScheduleResult(wos=[], tasks=[task], dependencies=[], conflicts=[])
    conflicts = detect_conflicts(inp, result)
    e4 = [c for c in conflicts if c.code == "E4"]
    assert e4, "expected E4 when hours exceed calendar limit"
    c = e4[0]
    assert c.level == ConflictLv.YELLOW
    assert c.group_code == GroupCode.MOLD.value
    assert c.cell_date == d
    assert c.hours_wall_total is not None and c.hours_wall_limit is not None
    assert c.hours_wall_total > c.hours_wall_limit
    assert "超限 +" in c.message
    assert "h / 日上限" in c.message
