"""顶层编排 schedule(ScheduleInput) → ScheduleResult。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.backward import apply_plan_dates, backward_place, seed_occupied
from engine.conflicts import detect_conflicts, enrich_unplaced_earliest
from engine.expand import expand_order, expand_semi
from engine.models import (
    Order,
    ScheduleConfig,
    ScheduleInput,
    ScheduleResult,
    SortMode,
    Wo,
    WoDependency,
    WoStatus,
    WoType,
)


def _clamp01(value: Decimal) -> Decimal:
    if value < 0:
        return Decimal(0)
    if value > 1:
        return Decimal(1)
    return value


def priority_score(order: Order, today: date, config: ScheduleConfig, max_amount: Decimal) -> Decimal:
    """BR-46：权重来自 config/weights.yaml，禁止硬编码。"""
    days = Decimal((order.due_date - today).days)
    horizon = Decimal(config.horizon_days)
    urgency = _clamp01(Decimal(1) - days / horizon)
    level = Decimal(order.customer_level) / Decimal(5)
    amount_ratio = (order.amount / max_amount) if max_amount > 0 else Decimal(0)
    is_ready = Decimal(1) if (order.ready_date is not None and order.ready_date <= today) else Decimal(0)
    is_strategic = Decimal(0)
    w = config.weights
    return (
        w.urgency * urgency
        + w.customer_level * level
        + w.amount * amount_ratio
        + w.ready * is_ready
        + w.strategic * is_strategic
    )


def sort_work_orders(wos: list[Wo], sort_mode: SortMode, pinned_wo_nos: list[str]) -> list[Wo]:
    """BR-25：默认 DUE_DESC。PIN_FIRST / DUE_ASC 阶段 3 使用。"""
    pinned = set(pinned_wo_nos)

    def key(wo: Wo) -> tuple:
        due_ord = wo.due_date.toordinal()
        score = wo.priority_score
        if sort_mode == SortMode.PIN_FIRST:
            return (0 if wo.wo_no in pinned else 1, -due_ord, -score, wo.wo_no)
        if sort_mode == SortMode.DUE_ASC:
            return (due_ord, -score, wo.wo_no)
        return (-due_ord, -score, wo.wo_no)

    return sorted(wos, key=key)


def _schedule_wos(
    wos: list[Wo],
    inp: ScheduleInput,
    occupied: dict,
    next_task_id: int,
) -> tuple[list, list, int]:
    tasks: list = []
    unplaced: list = []
    for wo in wos:
        if wo.is_locked:
            continue
        batch, miss, next_task_id = backward_place(wo, inp, occupied, next_task_id)
        apply_plan_dates(wo, batch)
        if batch:
            wo.status = WoStatus.PLANNED
        tasks.extend(batch)
        if miss is not None:
            unplaced.append(miss)
    return tasks, unplaced, next_task_id


def schedule(inp: ScheduleInput) -> ScheduleResult:
    """纯函数倒排。先成品后半成品（BR-34）。不写 so_order.due_date。"""
    occupied = seed_occupied(inp)
    orders_by_no = {o.order_no: o for o in inp.orders}
    max_amount = max((o.amount for o in inp.orders), default=Decimal(0))

    finished: list[Wo] = []
    skipped: list[str] = []
    for order in inp.orders:
        item = inp.items.get(order.item_code)
        if item is None or not item.computable:
            skipped.append(order.order_no)
            continue
        sph = inp.sph.get((order.item_code, item.group_code.value))
        wo = expand_order(
            order,
            item,
            inp.converts_for(order.item_code),
            inp.today,
            sph=sph,
        )
        if wo is None:
            skipped.append(order.order_no)
            continue
        src = orders_by_no[order.order_no]
        wo.priority_score = priority_score(src, inp.today, inp.config, max_amount)
        finished.append(wo)

    ordered_finished = sort_work_orders(finished, inp.config.sort_mode, inp.config.pinned_wo_nos)

    all_tasks: list = []
    unplaced: list = []
    next_task_id = 1
    fin_tasks, fin_unplaced, next_task_id = _schedule_wos(
        ordered_finished, inp, occupied, next_task_id
    )
    all_tasks.extend(fin_tasks)
    unplaced.extend(fin_unplaced)

    semi_wos: list[Wo] = []
    dependencies: list[WoDependency] = []
    for fwo in ordered_finished:
        route = inp.routes.get(fwo.item_code)
        if route is None or not route.needs_semi:
            continue
        finished_item = inp.items[fwo.item_code]
        semi_code = route.semi_item_code
        if semi_code is None:
            continue
        semi_item = inp.items[semi_code]
        sph_semi = inp.sph.get((semi_code, semi_item.group_code.value))
        semi = expand_semi(
            fwo,
            route,
            finished_item,
            semi_item,
            inp.stock,
            inp.today,
            sph=sph_semi,
        )
        if semi is None:
            continue
        semi.priority_score = fwo.priority_score
        semi_wos.append(semi)
        dependencies.append(
            WoDependency(
                pred_wo_no=semi.wo_no,
                succ_wo_no=fwo.wo_no,
                dep_type="FS",
                offset_days=route.lead_time_days,
            )
        )

    ordered_semi = sort_work_orders(semi_wos, inp.config.sort_mode, inp.config.pinned_wo_nos)
    semi_tasks, semi_unplaced, next_task_id = _schedule_wos(
        ordered_semi, inp, occupied, next_task_id
    )
    all_tasks.extend(semi_tasks)
    unplaced.extend(semi_unplaced)

    all_wos = ordered_finished + ordered_semi
    all_tasks.sort(key=lambda t: (t.task_date, t.wo_no, t.task_id))

    result = ScheduleResult(
        wos=all_wos,
        tasks=all_tasks,
        dependencies=dependencies,
        conflicts=[],
        unplaced=unplaced,
        skipped=skipped,
    )
    enrich_unplaced_earliest(inp, result)
    result.conflicts = detect_conflicts(inp, result)
    return result
