"""交互式试算：人手提示只扫触达组×日。"""

from __future__ import annotations

from datetime import date

from engine.interactive import headcount_warnings
from engine.models import GroupCode
from tests.conftest import TODAY, build_schedule_input, load_seed
from decimal import Decimal


def test_headcount_only_cells_excludes_unscoped_mold_oct():
    seed = load_seed()
    inp = build_schedule_input(
        seed,
        today=TODAY,
        reserved_ratio=Decimal("0"),
        order_nos=[f"SO-{i:03d}" for i in range(1, 10)],
    )
    from engine.schedule import schedule

    result = schedule(inp)
    mold_oct = date(2026, 10, 1)
    fake_mold_cell = (
        "FINISHED_DEPT",
        "MOLD",
        mold_oct,
    )
    # 全表扫描时可能产生多格提示；仅扫手工组某日时不应出现 10 月模具组
    manual_task = next(
        t for t in result.tasks if t.group_code == GroupCode.MANUAL
    )
    manual_day = manual_task.task_date
    manual_dept = manual_task.dept or "FINISHED_DEPT"
    scoped = headcount_warnings(
        inp,
        result.tasks,
        only_cells={(manual_dept, GroupCode.MANUAL.value, manual_day)},
    )
    assert not any(
        w.get("group_code") == "MOLD" and str(w.get("work_date", "")).startswith("2026-10")
        for w in scoped
    )
    # 构造假警告：only_cells 路径不会生成未扫描格
    assert fake_mold_cell not in {
        (w.get("dept", "FINISHED_DEPT"), w.get("group_code"), w.get("work_date"))
        for w in scoped
    }
