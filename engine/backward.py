"""倒排落位（BR-20 ~ BR-24）。"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from engine.capacity import day_capacity, hours_man, hours_wall, is_workday
from engine.errors import SchedulingLoopError, SphMissingError
from engine.models import GroupCode, ScheduleInput, Unplaced, Wo, WoTask

GUARD_LIMIT = 365


def _occupied_key(group_code: GroupCode, work_date: date) -> tuple[str, date]:
    return (group_code.value, work_date)


def seed_occupied(inp: ScheduleInput) -> dict[tuple[str, date], int]:
    """锁定/已下发任务先占位（BR-26）。"""
    occupied: dict[tuple[str, date], int] = {}
    for task in inp.locked_tasks:
        key = _occupied_key(task.group_code, task.task_date)
        occupied[key] = occupied.get(key, 0) + task.qty_board
    return occupied


def backward_place(
    wo: Wo,
    inp: ScheduleInput,
    occupied: dict[tuple[str, date], int],
    next_task_id: int,
) -> tuple[list[WoTask], Unplaced | None, int]:
    """从交期往回填，返回 (tasks, unplaced, next_task_id)。

    cursor < earliest 仍有余量 → Unplaced E1（BR-21），不 raise（BR-50）。
    """
    try:
        sph = inp.sph_of(wo.item_code, wo.group_code)
    except KeyError as exc:
        raise SphMissingError(f"缺少 SPH: {wo.item_code}/{wo.group_code.value}") from exc

    converts = inp.converts_for(wo.item_code)
    remaining = wo.qty_board_plan
    cursor = wo.due_date
    tasks: list[WoTask] = []
    guard = 0

    while remaining > 0:
        guard += 1
        if guard > GUARD_LIMIT:
            raise SchedulingLoopError(f"{wo.wo_no} 倒排超过 {GUARD_LIMIT} 步")

        if cursor < wo.earliest_start:
            unplaced = Unplaced(
                wo_no=wo.wo_no,
                code="E1",
                remaining=remaining,
                reason="未在最早可排日前安置完",
            )
            return tasks, unplaced, next_task_id

        if not is_workday(inp.calendar, wo.group_code, cursor):
            cursor -= timedelta(days=1)
            continue

        cap = day_capacity(
            inp.calendar,
            wo.group_code,
            cursor,
            sph,
            wo.crew_plan,
            converts,
            inp.config.reserved_ratio,
        )
        free = cap - occupied.get(_occupied_key(wo.group_code, cursor), 0)
        if free <= 0:
            cursor -= timedelta(days=1)
            continue

        qty = min(remaining, free)
        wall = hours_wall(qty, sph, wo.crew_plan, converts)
        task = WoTask(
            task_id=next_task_id,
            wo_no=wo.wo_no,
            group_code=wo.group_code,
            task_date=cursor,
            qty_board=qty,
            hours_wall=wall,
            hours_man=hours_man(wall, wo.crew_plan),
            crew_plan=wo.crew_plan,
            seq=1,
        )
        next_task_id += 1
        tasks.append(task)
        key = _occupied_key(wo.group_code, cursor)
        occupied[key] = occupied.get(key, 0) + qty
        remaining -= qty
        cursor -= timedelta(days=1)

    tasks.sort(key=lambda t: t.task_date)
    for seq, task in enumerate(tasks, start=1):
        task.seq = seq
    return tasks, None, next_task_id


def apply_plan_dates(wo: Wo, tasks: list[WoTask]) -> Wo:
    """只写开工/完工日，绝不写回订单交期（BR-27）。"""
    if not tasks:
        return wo
    wo.plan_start = min(t.task_date for t in tasks)
    wo.plan_end = max(t.task_date for t in tasks)
    return wo
