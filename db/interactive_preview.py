"""交互式试算：重算工时、冲突、diff、人手提示。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from db.snapshot import load_schedule_input
from engine.conflicts import detect_conflicts
from engine.diff import diff
from engine.interactive import apply_interactive_patch
from engine.models import ScheduleResult, Wo, WoTask


def _result_from_payload(wos: list[dict], tasks: list[dict]) -> ScheduleResult:
    return ScheduleResult(
        wos=[Wo.model_validate(w) for w in wos],
        tasks=[WoTask.model_validate(t) for t in tasks],
    )


def _order_impacts(
    baseline: ScheduleResult,
    new: ScheduleResult,
    trigger_order_no: str | None,
) -> list[dict]:
    base_map = {w.wo_no: w for w in baseline.wos}
    new_map = {w.wo_no: w for w in new.wos}
    orders: dict[str, dict] = {}

    def touch(order_no: str, wo_no: str) -> None:
        if order_no not in orders:
            b_wo = next((w for w in baseline.wos if w.source_order_no == order_no), None)
            n_wo = next((w for w in new.wos if w.source_order_no == order_no), None)
            orders[order_no] = {
                "order_no": order_no,
                "due_date": (n_wo or b_wo).due_date.isoformat() if (n_wo or b_wo) else None,
                "plan_start_before": b_wo.plan_start.isoformat() if b_wo and b_wo.plan_start else None,
                "plan_end_before": b_wo.plan_end.isoformat() if b_wo and b_wo.plan_end else None,
                "plan_start_after": n_wo.plan_start.isoformat() if n_wo and n_wo.plan_start else None,
                "plan_end_after": n_wo.plan_end.isoformat() if n_wo and n_wo.plan_end else None,
                "is_trigger": order_no == trigger_order_no,
            }

    for wo_no in set(base_map) | set(new_map):
        b = base_map.get(wo_no)
        n = new_map.get(wo_no)
        if b is None and n is None:
            continue
        order_no = (n or b).source_order_no  # type: ignore[union-attr]
        if (
            (b is None or n is None)
            or b.plan_start != n.plan_start
            or b.plan_end != n.plan_end
        ):
            touch(order_no, wo_no)

    if trigger_order_no and trigger_order_no not in orders:
        touch(trigger_order_no, "")

    return sorted(orders.values(), key=lambda x: (not x["is_trigger"], x["order_no"]))


def _cell_key(t: WoTask) -> tuple[str, str, date]:
    return (t.dept.value, t.group_code.value, t.task_date)


def _affected_cells(
    baseline_tasks: list[WoTask],
    proposed_tasks: list[WoTask],
    trigger_task_id: int | None = None,
) -> set[tuple[str, str, date]]:
    """本次调整触达的工作中心×日（含迁出/迁入格）。"""
    base_by_id = {t.task_id: t for t in baseline_tasks}
    cells: set[tuple[str, str, date]] = set()
    for p in proposed_tasks:
        b = base_by_id.get(p.task_id)
        if b is None:
            cells.add(_cell_key(p))
            continue
        if (
            b.dept != p.dept
            or b.group_code != p.group_code
            or b.task_date != p.task_date
            or b.crew_plan != p.crew_plan
            or b.qty_board != p.qty_board
        ):
            cells.add(_cell_key(b))
            cells.add(_cell_key(p))
    if trigger_task_id is not None:
        t = next((x for x in proposed_tasks if x.task_id == trigger_task_id), None)
        if t:
            cells.add(_cell_key(t))
    return cells


def _filter_headcount_warnings(
    warnings: list[dict],
    cells: set[tuple[str, str, date]],
    proposed_tasks: list[WoTask],
) -> list[dict]:
    """兜底：再按触达格滤一遍。"""
    iso_cells = {(d, g, dt.isoformat()) for d, g, dt in cells}
    out: list[dict] = []
    for w in warnings:
        d = w.get("dept")
        g = w.get("group_code")
        wd = w.get("work_date")
        if d and g and wd and (d, g, wd) in iso_cells:
            out.append(w)
            continue
        tid = w.get("task_id")
        if tid is not None:
            t = next((x for x in proposed_tasks if x.task_id == tid), None)
            if t and _cell_key(t) in cells:
                out.append(w)
    return out


def run_interactive_preview(
    session: Session,
    *,
    today: date,
    order_nos: list[str],
    baseline_wos: list[dict],
    baseline_tasks: list[dict],
    proposed_wos: list[dict],
    proposed_tasks: list[dict],
    trigger_task_id: int | None = None,
    reserved_ratio: Decimal = Decimal("0"),
) -> dict:
    inp = load_schedule_input(
        session,
        today=today,
        order_nos=order_nos,
        reserved_ratio=reserved_ratio,
    )
    baseline = _result_from_payload(baseline_wos, baseline_tasks)
    proposed_wos_models = [Wo.model_validate(w) for w in proposed_wos]
    proposed_tasks_models = [WoTask.model_validate(t) for t in proposed_tasks]

    baseline_tasks_models = [WoTask.model_validate(t) for t in baseline_tasks]
    warning_cells = _affected_cells(
        baseline_tasks_models,
        proposed_tasks_models,
        trigger_task_id,
    )
    new_result, headcount_warnings = apply_interactive_patch(
        inp,
        proposed_wos_models,
        proposed_tasks_models,
        warning_cells=warning_cells,
    )
    new_result.conflicts = detect_conflicts(inp, new_result)
    diff_result = diff(baseline, new_result, today)
    headcount_warnings = _filter_headcount_warnings(
        headcount_warnings,
        warning_cells,
        proposed_tasks_models,
    )

    trigger_order_no: str | None = None
    if trigger_task_id is not None:
        t = next((x for x in proposed_tasks_models if x.task_id == trigger_task_id), None)
        if t:
            wo = next((w for w in new_result.wos if w.wo_no == t.wo_no), None)
            if wo:
                trigger_order_no = wo.source_order_no

    return {
        "baseline": baseline.model_dump(mode="json"),
        "result": new_result.model_dump(mode="json"),
        "diff": diff_result.model_dump(mode="json"),
        "conflicts": [c.model_dump(mode="json") for c in new_result.conflicts],
        "headcount_warnings": headcount_warnings,
        "order_impacts": _order_impacts(baseline, new_result, trigger_order_no),
        "trigger_order_no": trigger_order_no,
    }
