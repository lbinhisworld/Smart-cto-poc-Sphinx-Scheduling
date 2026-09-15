"""交互式调整：工时重算、人手校验。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.interactive import apply_interactive_patch, headcount_warnings, recalculate_task_hours
from engine.models import GroupCode, WoTask
from tests.conftest import TODAY, build_schedule_input, load_seed
from tests.helpers import tasks_of


def _run_so001():
    seed = load_seed()
    inp = build_schedule_input(seed, today=TODAY, reserved_ratio=Decimal("0"), order_nos=["SO-001"])
    from engine.schedule import schedule

    return inp, schedule(inp)


def test_recalculate_hours_when_crew_doubles():
    inp, result = _run_so001()
    t0 = result.tasks[0]
    patched = t0.model_copy(update={"crew_plan": 6})
    tasks = [patched if t.task_id == t0.task_id else t for t in result.tasks]
    new_tasks = recalculate_task_hours(inp, result.wos, tasks)
    t_new = next(t for t in new_tasks if t.task_id == t0.task_id)
    t_old_wall = t0.hours_wall
    assert t_new.hours_wall < t_old_wall
    # SINGLE 口径：墙钟减半，人·时总量大致不变
    assert abs(t_new.hours_man - t0.hours_man) < Decimal("0.01")


def test_headcount_warn_when_crew_exceeds_group():
    inp, result = _run_so001()
    t0 = result.tasks[0]
    tasks = [t0.model_copy(update={"crew_plan": 99})]
    warns = headcount_warnings(inp, tasks)
    assert any(w["code"] == "CREW_OVER_HEAD" for w in warns)


def test_interactive_patch_updates_plan_end():
    inp, result = _run_so001()
    t0 = result.tasks[0]
    moved = t0.model_copy(update={"task_date": date(2026, 9, 20)})
    tasks = [moved if t.task_id == t0.task_id else t for t in result.tasks]
    new_result, _ = apply_interactive_patch(inp, result.wos, tasks)
    p1_wo = next(w for w in new_result.wos if w.item_code == "P1")
    assert p1_wo.plan_end == date(2026, 9, 23)
    assert any(d == date(2026, 9, 20) for d, _ in tasks_of(new_result, "P1"))
