"""变动死区（BR-42）：位移或工时变化过小则保持基线任务。"""

from __future__ import annotations

from decimal import Decimal

from engine.models import ScheduleConfig, ScheduleInput, ScheduleResult, WoTask


def _hours_total(tasks: list[WoTask]) -> Decimal:
    return sum((t.hours_wall for t in tasks), Decimal(0))


def apply_deadband(
    inp: ScheduleInput,
    result: ScheduleResult,
) -> ScheduleResult:
    """对比 baseline，对非触发工单在死区内恢复原任务行。"""
    baseline = inp.baseline
    if baseline is None:
        return result

    triggers = set(inp.deadband_trigger_wo_nos) | set(inp.config.pinned_wo_nos)
    base_wos = {wo.wo_no: wo for wo in baseline.wos}
    base_tasks: dict[str, list[WoTask]] = {}
    for task in baseline.tasks:
        base_tasks.setdefault(task.wo_no, []).append(task)

    cfg = inp.config
    kept_tasks: list[WoTask] = []
    other_tasks: list[WoTask] = []
    restore_wo_nos: set[str] = set()

    for wo in result.wos:
        if wo.wo_no in triggers:
            continue
        base = base_wos.get(wo.wo_no)
        old_tasks = base_tasks.get(wo.wo_no, [])
        new_tasks = [t for t in result.tasks if t.wo_no == wo.wo_no]
        if base is None or not old_tasks:
            continue
        old_start = base.plan_start
        new_start = wo.plan_start
        if old_start is None or new_start is None:
            continue
        day_shift = abs((new_start - old_start).days)
        old_h = _hours_total(old_tasks)
        new_h = _hours_total(new_tasks)
        if old_h <= 0:
            ratio_ok = True
        else:
            ratio_ok = abs(new_h - old_h) / old_h < cfg.deadband_hours_ratio
        if day_shift < cfg.deadband_days or ratio_ok:
            restore_wo_nos.add(wo.wo_no)
            wo.plan_start = base.plan_start
            wo.plan_end = base.plan_end
            wo.qty_board_plan = base.qty_board_plan

    for task in result.tasks:
        if task.wo_no in restore_wo_nos:
            continue
        other_tasks.append(task)

    for wo_no in restore_wo_nos:
        for task in base_tasks.get(wo_no, []):
            kept_tasks.append(task.model_copy(deep=True))

    merged_tasks = kept_tasks + other_tasks
    merged_tasks.sort(key=lambda t: (t.task_date, t.wo_no, t.task_id))
    result.tasks = merged_tasks
    return result
