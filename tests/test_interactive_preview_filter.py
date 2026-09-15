"""交互式 preview：人手提示仅保留触达组×日。"""

from __future__ import annotations

from datetime import timedelta

from db.interactive_preview import _affected_cells, _filter_headcount_warnings
from tests.test_interactive import _run_so001


def test_filter_headcount_warnings_drops_unrelated_mold_oct():
    _, result = _run_so001()
    t0 = result.tasks[0]
    moved = t0.model_copy(update={"task_date": t0.task_date - timedelta(days=1)})
    proposed = [moved if t.task_id == t0.task_id else t for t in result.tasks]
    baseline = list(result.tasks)
    cells = _affected_cells(baseline, proposed, t0.task_id)

    unrelated_oct = {
        "code": "CREW_OVER_HEAD",
        "level": "warn",
        "message": "模具组 2026-10-15 人手超限",
        "dept": "FINISHED_DEPT",
        "group_code": "MOLD",
        "work_date": "2026-10-15",
    }
    on_old_cell = {
        "code": "WALL_OVER",
        "level": "warn",
        "message": "触达旧格",
        "dept": t0.dept.value,
        "group_code": t0.group_code.value,
        "work_date": t0.task_date.isoformat(),
    }
    on_new_cell = {
        "code": "WALL_OVER",
        "level": "warn",
        "message": "触达新格",
        "dept": moved.dept.value,
        "group_code": moved.group_code.value,
        "work_date": moved.task_date.isoformat(),
    }

    filtered = _filter_headcount_warnings(
        [unrelated_oct, on_old_cell, on_new_cell],
        cells,
        proposed,
    )
    messages = {w["message"] for w in filtered}
    assert "模具组 2026-10-15 人手超限" not in messages
    assert "触达旧格" in messages
    assert "触达新格" in messages
