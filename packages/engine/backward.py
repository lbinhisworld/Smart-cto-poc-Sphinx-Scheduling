"""倒排落位（BR-20 ~ BR-24）。"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN

from engine.capacity import (
    available_person_hours,
    day_capacity,
    hours_man,
    hours_wall,
    is_workday,
    sph_board_rate,
)
from engine.errors import SchedulingLoopError, SphMissingError
from engine.models import ScheduleInput, SphBasis, TraceAct, TraceEvent, Unplaced, Wo, WoTask
from engine.trace import append_event, place_message, unplaced_audit_message
from engine.work_center import wc_key

GUARD_LIMIT = 365
_MAN_Q = Decimal("0.0001")


class DayLoad:
    """同一组日上，单人口径占人·时，多人配合占版，两套不相加。"""

    def __init__(self) -> None:
        self.boards: dict[tuple[str, str, date], int] = {}
        self.man: dict[tuple[str, str, date], Decimal] = {}


def _basis_for_task(inp: ScheduleInput, task: WoTask, wos: list[Wo]) -> SphBasis:
    by_wo = {wo.wo_no: wo for wo in wos}
    wo = by_wo.get(task.wo_no)
    if wo is not None:
        try:
            return inp.sph_of(wo.item_code, task.group_code).sph_basis
        except KeyError:
            pass
    bases = {
        row.sph_basis
        for (item_code, group_code), row in inp.sph.items()
        if group_code == task.group_code.value and item_code
    }
    if bases == {SphBasis.CREW}:
        return SphBasis.CREW
    return SphBasis.SINGLE


def seed_occupied(inp: ScheduleInput, wos: list[Wo] | None = None) -> DayLoad:
    """锁定/已下发任务先占位（BR-26）。"""
    load = DayLoad()
    known = list(wos or [])
    for task in inp.locked_tasks:
        key = wc_key(task.dept, task.group_code, task.task_date)
        if _basis_for_task(inp, task, known) == SphBasis.CREW:
            load.boards[key] = load.boards.get(key, 0) + task.qty_board
        else:
            load.man[key] = load.man.get(key, Decimal(0)) + task.hours_man
    return load


def _crew_sets(inp: ScheduleInput, wo: Wo) -> int:
    raw = inp.crew_sets.get(f"{wo.dept.value}|{wo.group_code.value}", 1)
    return raw if raw > 0 else 1


def backward_place(
    wo: Wo,
    inp: ScheduleInput,
    occupied: DayLoad,
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
            crew_sets=_crew_sets(inp, wo),
        )
        key = wc_key(wo.dept, wo.group_code, cursor)
        if sph.sph_basis == SphBasis.SINGLE:
            rate = sph_board_rate(sph, converts)
            avail_man = available_person_hours(
                inp.calendar,
                wo.dept,
                wo.group_code,
                cursor,
                inp.config.reserved_ratio,
                inp.capacity_overrides,
            )
            used_man = occupied.man.get(key, Decimal(0))
            free_man = avail_man - used_man
            free = (
                int((free_man * rate).to_integral_value(rounding=ROUND_DOWN))
                if rate > 0 and free_man > 0
                else 0
            )
            occupied_before = cap - free if cap >= free else 0
        else:
            occupied_before = occupied.boards.get(key, 0)
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
        if sph.sph_basis == SphBasis.SINGLE:
            rate = sph_board_rate(sph, converts)
            consumed = (Decimal(qty) / rate).quantize(_MAN_Q) if rate > 0 else Decimal(0)
            occupied.man[key] = occupied.man.get(key, Decimal(0)) + consumed
        else:
            occupied.boards[key] = occupied.boards.get(key, 0) + qty
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
