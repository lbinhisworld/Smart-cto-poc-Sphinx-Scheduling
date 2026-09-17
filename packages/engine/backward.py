"""倒排落位（BR-20 ~ BR-24）。"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from engine.capacity import day_capacity, hours_man, hours_wall, is_workday
from engine.errors import SchedulingLoopError, SphMissingError
from engine.models import ScheduleInput, TraceAct, TraceEvent, Unplaced, Wo, WoTask
from engine.trace import append_event, place_message, unplaced_audit_message
from engine.work_center import wc_key

GUARD_LIMIT = 365


def seed_occupied(inp: ScheduleInput) -> dict[tuple[str, str, date], int]:
    """锁定/已下发任务先占位（BR-26）。"""
    occupied: dict[tuple[str, str, date], int] = {}
    for task in inp.locked_tasks:
        key = wc_key(task.dept, task.group_code, task.task_date)
        occupied[key] = occupied.get(key, 0) + task.qty_board
    return occupied


def backward_place(
    wo: Wo,
    inp: ScheduleInput,
    occupied: dict[tuple[str, str, date], int],
    next_task_id: int,
    trace: list[TraceEvent] | None = None,
    trace_act: TraceAct = TraceAct.PLACE,
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
    attempts: list[dict] = []
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
            append_event(
                trace,
                act=trace_act,
                kind="unplaced",
                message=unplaced_audit_message(
                    order_no=wo.source_order_no,
                    item_code=wo.item_code,
                    due_date=wo.due_date,
                    earliest_start=wo.earliest_start,
                    remaining=remaining,
                    attempts=attempts,
                ),
                order_no=wo.source_order_no,
                wo_no=wo.wo_no,
                wo_type=wo.wo_type.value,
                item_code=wo.item_code,
                qty_board=remaining,
                due_date=wo.due_date,
                task_date=wo.earliest_start,
                skip_reason="BEFORE_EARLIEST",
            )
            return tasks, unplaced, next_task_id

        if not is_workday(inp.calendar, wo.dept, wo.group_code, cursor):
            attempts.append({"date": cursor, "kind": "skip", "reason": "REST"})
            append_event(
                trace,
                act=trace_act,
                kind="skip_day",
                message=f"{cursor.isoformat()} 非工作日，再往前一天",
                order_no=wo.source_order_no,
                wo_no=wo.wo_no,
                wo_type=wo.wo_type.value,
                item_code=wo.item_code,
                dept=wo.dept.value,
                group_code=wo.group_code.value,
                task_date=cursor,
                skip_reason="REST",
            )
            cursor -= timedelta(days=1)
            continue

        cap = day_capacity(
            inp.calendar,
            wo.dept,
            wo.group_code,
            cursor,
            sph,
            wo.crew_plan,
            converts,
            inp.config.reserved_ratio,
            inp.capacity_overrides,
        )
        key = wc_key(wo.dept, wo.group_code, cursor)
        occupied_before = occupied.get(key, 0)
        free = cap - occupied_before
        if free <= 0:
            attempts.append({"date": cursor, "kind": "skip", "reason": "FULL", "cap": cap})
            append_event(
                trace,
                act=trace_act,
                kind="skip_day",
                message=f"{cursor.isoformat()} 产能已满（上限 {cap} 版），再往前一天",
                order_no=wo.source_order_no,
                wo_no=wo.wo_no,
                wo_type=wo.wo_type.value,
                item_code=wo.item_code,
                dept=wo.dept.value,
                group_code=wo.group_code.value,
                task_date=cursor,
                cap_board=cap,
                occupied_before=occupied_before,
                free_before=0,
                skip_reason="FULL",
            )
            cursor -= timedelta(days=1)
            continue

        qty = min(remaining, free)
        wall = hours_wall(qty, sph, wo.crew_plan, converts)
        task = WoTask(
            task_id=next_task_id,
            wo_no=wo.wo_no,
            dept=wo.dept,
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
        occupied[key] = occupied.get(key, 0) + qty
        remaining -= qty
        attempts.append(
            {"date": cursor, "kind": "place", "qty": qty, "cap": cap, "occupied": occupied_before}
        )
        append_event(
            trace,
            act=trace_act,
            kind="place",
            message=place_message(
                order_no=wo.source_order_no,
                item_code=wo.item_code,
                task_date=cursor,
                qty=qty,
                remaining=remaining,
                free_before=free,
                occupied_before=occupied_before,
                cap=cap,
            ),
            order_no=wo.source_order_no,
            wo_no=wo.wo_no,
            wo_type=wo.wo_type.value,
            item_code=wo.item_code,
            dept=wo.dept.value,
            group_code=wo.group_code.value,
            task_date=cursor,
            task_id=task.task_id,
            qty_board=qty,
            remaining_after=remaining,
            cap_board=cap,
            occupied_before=occupied_before,
            free_before=free,
        )
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
