"""插单可行性与四策略（BR-40~47）。"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

from engine.diff import diff
from engine.expand import expand_order
from engine.models import (
    FeasibilityResult,
    FeasibilityStatus,
    InsertCompareResult,
    InsertStrategy,
    InsertStrategyOutcome,
    Item,
    ItemRoute,
    Order,
    ScheduleInput,
    ScheduleResult,
    SortMode,
    WoType,
)
from engine.schedule import schedule


def check_insert_feasible(
    order: Order,
    item: Item,
    route: ItemRoute,
    stock: dict[str, Decimal],
    today,
) -> FeasibilityResult:
    """§7.2 插单物理可行性（先判定再排）。"""
    avail_days = (order.due_date - today).days
    if not item.computable:
        return FeasibilityResult(
            status=FeasibilityStatus.INFEASIBLE,
            message="缺少包/袋/箱换算率，不可自动排产",
        )
    if route.needs_semi and route.semi_item_code and route.semi_board_per_box:
        gross = int(
            (
                order.qty_order
                * route.semi_board_per_box
                * (Decimal(1) + item.loss_rate)
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        if stock.get(route.semi_item_code, Decimal(0)) >= gross:
            return FeasibilityResult(
                status=FeasibilityStatus.OK_WITH_WARN,
                message="占用半成品库存，可能影响其他单的预留",
            )
        if avail_days < route.lead_time_days:
            return FeasibilityResult(
                status=FeasibilityStatus.INFEASIBLE,
                message=f"半成品提前期需 {route.lead_time_days} 天，可用 {avail_days} 天，物理不可行",
            )
        return FeasibilityResult(status=FeasibilityStatus.OK, message="可试排")
    if avail_days < 1:
        return FeasibilityResult(status=FeasibilityStatus.INFEASIBLE, message="交期早于今天")
    return FeasibilityResult(status=FeasibilityStatus.OK, message="可试排")


def _merged_finished(baseline: ScheduleResult, new_wo) -> list:
    base = [wo.model_copy(deep=True) for wo in baseline.wos if wo.wo_type == WoType.FINISHED]
    return base + [new_wo.model_copy(deep=True)]


def _run_strategy(
    inp: ScheduleInput,
    baseline: ScheduleResult,
    merged_finished: list,
    new_wo_no: str,
    strategy: InsertStrategy,
) -> ScheduleResult:
    cfg = inp.config.model_copy(deep=True)
    cfg.insert_strategy = strategy
    reserved = inp.config.reserved_ratio

    if strategy in (InsertStrategy.B, InsertStrategy.C):
        cfg.sort_mode = SortMode.PIN_FIRST
        cfg.pinned_wo_nos = [new_wo_no]
    else:
        cfg.sort_mode = SortMode.DUE_DESC
        cfg.pinned_wo_nos = []

    if strategy == InsertStrategy.A:
        reserved = Decimal("0")

    trial = inp.model_copy(
        update={
            "orders": [],
            "finished_override": merged_finished,
            "config": cfg,
            "baseline": None,
            "deadband_trigger_wo_nos": [],
            "capacity_overrides": list(inp.capacity_overrides),
        }
    )
    trial.config.reserved_ratio = reserved
    return schedule(trial)


def schedule_insert(
    inp: ScheduleInput,
    urgent_order: Order,
    *,
    baseline: ScheduleResult | None = None,
) -> InsertCompareResult:
    """四策略试排 + diff（复用同一 schedule()）。"""
    item = inp.items[urgent_order.item_code]
    route = inp.routes[urgent_order.item_code]
    feasibility = check_insert_feasible(
        urgent_order, item, route, inp.stock, inp.today
    )

    if baseline is None:
        baseline = schedule(inp.model_copy(update={"orders": [], "finished_override": None}))

    sph = inp.sph.get((urgent_order.item_code, item.group_code.value))
    new_wo = expand_order(
        urgent_order,
        item,
        inp.converts_for(urgent_order.item_code),
        inp.today,
        sph=sph,
    )
    assert new_wo is not None
    merged = _merged_finished(baseline, new_wo)

    outcomes: list[InsertStrategyOutcome] = []
    for strategy in (InsertStrategy.A, InsertStrategy.B, InsertStrategy.C, InsertStrategy.D):
        result = _run_strategy(inp, baseline, merged, new_wo.wo_no, strategy)
        d = diff(baseline, result, inp.today)
        outcomes.append(InsertStrategyOutcome(strategy=strategy, result=result, diff=d))

    main = next(o for o in outcomes if o.strategy == InsertStrategy.B)
    return InsertCompareResult(
        strategies=outcomes,
        diff=main.diff,
        feasibility=feasibility,
    )
