"""顶层编排 schedule(ScheduleInput) → ScheduleResult。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from engine.backward import apply_plan_dates, backward_place, seed_occupied
from engine.conflicts import detect_conflicts, enrich_unplaced_earliest
from engine.deadband import apply_deadband
from engine.component_expand import consume_purchased_line, expand_semi_from_line
from engine.expand import expand_order
from engine.kit_pool import KitSnapshot
from engine.kitting import build_kit_checks, detect_kit_conflicts
from engine.models import (
    ComponentRole,
    Order,
    ScheduleConfig,
    ScheduleInput,
    ScheduleResult,
    ScheduleTrace,
    SortMode,
    TraceAct,
    TraceEvent,
    Wo,
    WoDependency,
    WoStatus,
    WoType,
)
from engine.trace import append_event


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
    trace: list[TraceEvent] | None = None,
    trace_act: TraceAct = TraceAct.PLACE,
) -> tuple[list, list, int]:
    tasks: list = []
    unplaced: list = []
    for wo in wos:
        if wo.is_locked:
            locked_batch = [t for t in inp.locked_tasks if t.wo_no == wo.wo_no]
            apply_plan_dates(wo, locked_batch)
            if locked_batch:
                wo.status = WoStatus.PLANNED
            tasks.extend(locked_batch)
            continue
        batch, miss, next_task_id = backward_place(
            wo, inp, occupied, next_task_id, trace=trace, trace_act=trace_act
        )
        apply_plan_dates(wo, batch)
        if batch:
            wo.status = WoStatus.PLANNED
        tasks.extend(batch)
        if miss is not None:
            unplaced.append(miss)
    return tasks, unplaced, next_task_id


def _ripple_stats(baseline: ScheduleResult | None, result: ScheduleResult) -> tuple[int, bool]:
    if baseline is None:
        return 0, False
    base = {wo.wo_no: wo for wo in baseline.wos}
    affected = 0
    for wo in result.wos:
        old = base.get(wo.wo_no)
        if old is None:
            continue
        if old.plan_start != wo.plan_start or old.plan_end != wo.plan_end:
            affected += 1
    return affected, False


def schedule(inp: ScheduleInput) -> ScheduleResult:
    """纯函数倒排。先成品后半成品（BR-34）。不写 so_order.due_date。"""
    occupied = seed_occupied(inp)
    orders_by_no = {o.order_no: o for o in inp.orders}
    max_amount = max((o.amount for o in inp.orders), default=Decimal(0))
    events: list[TraceEvent] = []

    finished: list[Wo] = []
    skipped: list[str] = []
    if inp.finished_override is not None:
        finished = [wo.model_copy(deep=True) for wo in inp.finished_override]
    else:
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
            append_event(
                events,
                act=TraceAct.EXPAND,
                kind="expand_finished",
                message=(
                    f"{order.order_no} {order.item_code} · 订货 {order.qty_order} "
                    f"→ 计划 {wo.qty_board_plan} 版 · 交期 {order.due_date.isoformat()}"
                ),
                order_no=order.order_no,
                wo_no=wo.wo_no,
                wo_type=WoType.FINISHED.value,
                item_code=wo.item_code,
                qty_board=wo.qty_board_plan,
                due_date=order.due_date,
            )

    ordered_finished = sort_work_orders(finished, inp.config.sort_mode, inp.config.pinned_wo_nos)
    for i, wo in enumerate(ordered_finished, start=1):
        append_event(
            events,
            act=TraceAct.QUEUE,
            kind="queue_rank",
            message=(
                f"第 {i} 个占格：{wo.source_order_no} {wo.item_code} · "
                f"交期 {wo.due_date.isoformat()}（{inp.config.sort_mode.value}）"
            ),
            order_no=wo.source_order_no,
            wo_no=wo.wo_no,
            wo_type=wo.wo_type.value,
            item_code=wo.item_code,
            rank=i,
            due_date=wo.due_date,
        )

    all_tasks: list = []
    unplaced: list = []
    next_task_id = 1
    fin_tasks, fin_unplaced, next_task_id = _schedule_wos(
        ordered_finished,
        inp,
        occupied,
        next_task_id,
        trace=events,
        trace_act=TraceAct.PLACE,
    )
    all_tasks.extend(fin_tasks)
    unplaced.extend(fin_unplaced)

    semi_wos: list[Wo] = []
    dependencies: list[WoDependency] = []
    pool = KitSnapshot(inp.stock)
    lines_by_finished: dict[str, list] = {}
    orders_by_no = {o.order_no: o for o in inp.orders}

    for fwo in ordered_finished:
        order = orders_by_no.get(fwo.source_order_no)
        if order is None:
            continue
        finished_item = inp.items[fwo.item_code]
        bom = inp.bom_for(fwo.item_code)
        route = inp.routes.get(fwo.item_code)
        line_results: list = []

        if bom:
            semi_lines = [ln for ln in bom if ln.component_role == ComponentRole.SEMI]
            multi_semi = len(semi_lines) > 1
            for line in bom:
                if line.component_role == ComponentRole.PURCHASED:
                    lr = consume_purchased_line(order, line, finished_item, pool, inp.today)
                    line_results.append(lr)
                    append_event(
                        events,
                        act=TraceAct.SEMI,
                        kind="consume_purchased",
                        message=(
                            f"{order.order_no} 外购 {line.component_item_code} · "
                            f"占库 {lr.from_stock} 版"
                            + (f" · 缺 {lr.shortage_board} 版" if lr.shortage_board else " · 齐套")
                        ),
                        order_no=order.order_no,
                        wo_no=fwo.wo_no,
                        item_code=line.component_item_code,
                        qty_board=lr.from_stock,
                    )
                    continue
                comp = inp.items.get(line.component_item_code)
                if comp is None:
                    continue
                sph_semi = inp.sph.get((line.component_item_code, comp.group_code.value))
                semi, lr = expand_semi_from_line(
                    fwo,
                    order,
                    line,
                    finished_item,
                    comp,
                    pool,
                    inp.today,
                    sph_semi,
                    multi_semi_wo_suffix=multi_semi,
                )
                line_results.append(lr)
                if semi is None:
                    append_event(
                        events,
                        act=TraceAct.SEMI,
                        kind="semi_from_stock",
                        message=(
                            f"{order.order_no} 半成品 {line.component_item_code} "
                            f"库存已覆盖（毛 {lr.gross_board} / 占库 {lr.from_stock}），不生成工单"
                        ),
                        order_no=order.order_no,
                        wo_no=fwo.wo_no,
                        item_code=line.component_item_code,
                        qty_board=0,
                    )
                    continue
                append_event(
                    events,
                    act=TraceAct.SEMI,
                    kind="expand_semi",
                    message=(
                        f"{order.order_no} 半成品 {semi.item_code} 净需求 {semi.qty_board_plan} 版 · "
                        f"应交 {semi.due_date.isoformat()}（成品开工 − 提前期）"
                    ),
                    order_no=order.order_no,
                    wo_no=semi.wo_no,
                    wo_type=WoType.SEMI.value,
                    item_code=semi.item_code,
                    qty_board=semi.qty_board_plan,
                    due_date=semi.due_date,
                )
                semi.priority_score = fwo.priority_score
                semi_wos.append(semi)
                dependencies.append(
                    WoDependency(
                        pred_wo_no=semi.wo_no,
                        succ_wo_no=fwo.wo_no,
                        dep_type="FS",
                        offset_days=line.lead_time_days,
                    )
                )
            lines_by_finished[fwo.wo_no] = line_results

    ordered_semi = sort_work_orders(semi_wos, inp.config.sort_mode, inp.config.pinned_wo_nos)
    semi_tasks, semi_unplaced, next_task_id = _schedule_wos(
        ordered_semi,
        inp,
        occupied,
        next_task_id,
        trace=events,
        trace_act=TraceAct.SEMI,
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
        kit_allocations=list(pool.allocations),
    )
    enrich_unplaced_earliest(inp, result)
    result = apply_deadband(inp, result)
    affected, _ = _ripple_stats(inp.baseline, result)
    result.ripple_affected_count = affected
    result.ripple_limit_exceeded = affected > inp.config.ripple_limit
    result.kit_checks = build_kit_checks(inp, result, lines_by_finished)
    result.conflicts = detect_conflicts(inp, result)
    result.conflicts.extend(detect_kit_conflicts(inp, result))
    if result.ripple_limit_exceeded:
        from engine.models import Conflict, ConflictLv

        result.conflicts.append(
            Conflict(
                code="RIPPLE",
                level=ConflictLv.YELLOW,
                message=f"受影响工单 {affected} 超过涟漪上限 {inp.config.ripple_limit}，需分批确认",
                suggest="NOTIFY_SALES",
            )
        )
    red_n = sum(1 for c in result.conflicts if c.level.value == "RED")
    yel_n = sum(1 for c in result.conflicts if c.level.value == "YELLOW")
    append_event(
        events,
        act=TraceAct.CHECK,
        kind="check_summary",
        message=(
            f"体检完成：红 {red_n} · 黄 {yel_n} · 未安置 {len(result.unplaced)} 条。"
            "红色只提示不改交期，需人处理或协商销售。"
        ),
    )
    result.trace = ScheduleTrace(sort_mode=inp.config.sort_mode.value, events=events)
    return result
