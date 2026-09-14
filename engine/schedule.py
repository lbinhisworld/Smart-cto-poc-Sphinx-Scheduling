"""顶层编排 schedule(ScheduleInput) → ScheduleResult。

阶段 1：locked 占位 + 展开成品 + DUE_DESC + 倒排。半成品见阶段 2。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.backward import apply_plan_dates, backward_place, seed_occupied
from engine.expand import expand_order
from engine.models import (
    Order,
    ScheduleConfig,
    ScheduleInput,
    ScheduleResult,
    SortMode,
    Wo,
    WoStatus,
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


def schedule(inp: ScheduleInput) -> ScheduleResult:
    """纯函数倒排。today 只来自入参。不写 so_order.due_date。"""
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

    ordered = sort_work_orders(finished, inp.config.sort_mode, inp.config.pinned_wo_nos)

    all_tasks = []
    unplaced = []
    next_task_id = 1
    for wo in ordered:
        if wo.is_locked:
            continue
        tasks, miss, next_task_id = backward_place(wo, inp, occupied, next_task_id)
        apply_plan_dates(wo, tasks)
        wo.status = WoStatus.PLANNED
        all_tasks.extend(tasks)
        if miss is not None:
            unplaced.append(miss)

    all_tasks.sort(key=lambda t: (t.task_date, t.wo_no, t.task_id))
    return ScheduleResult(
        wos=ordered,
        tasks=all_tasks,
        dependencies=[],
        conflicts=[],
        unplaced=unplaced,
        skipped=skipped,
    )
