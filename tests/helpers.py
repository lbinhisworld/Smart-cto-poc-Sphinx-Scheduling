"""测试辅助：按品项/订单聚合 ScheduleResult。"""

from __future__ import annotations

from datetime import date

from engine.models import ConflictLv, ScheduleResult, Wo, WoType


def tasks_of(result: ScheduleResult, item_code: str) -> list[tuple[date, int]]:
    wo_nos = {wo.wo_no for wo in result.wos if wo.item_code == item_code}
    rows = [(t.task_date, t.qty_board) for t in result.tasks if t.wo_no in wo_nos]
    return sorted(rows)


def wo_by_order(result: ScheduleResult, order_no: str, wo_type: WoType | None = None) -> Wo | None:
    for wo in result.wos:
        if wo.source_order_no != order_no:
            continue
        if wo_type is not None and wo.wo_type != wo_type:
            continue
        return wo
    return None


def semi_wo_of(result: ScheduleResult, order_no: str) -> Wo | None:
    return wo_by_order(result, order_no, WoType.SEMI)


def finished_wo_of(result: ScheduleResult, order_no: str) -> Wo | None:
    return wo_by_order(result, order_no, WoType.FINISHED)


def has_conflict(
    result: ScheduleResult,
    code: str,
    *,
    level: ConflictLv | None = None,
) -> bool:
    for c in result.conflicts:
        if c.code != code:
            continue
        if level is not None and c.level != level:
            continue
        return True
    return False


def plan_start_of(result: ScheduleResult, item_code: str) -> date | None:
    for wo in result.wos:
        if wo.item_code == item_code and wo.wo_type == WoType.FINISHED:
            return wo.plan_start
    return None


def due_of(result: ScheduleResult, item_code: str) -> date | None:
    for wo in result.wos:
        if wo.item_code == item_code and wo.wo_type == WoType.FINISHED:
            return wo.due_date
    return None


def earliest_finish_from_result(result: ScheduleResult) -> date | None:
    for u in result.unplaced:
        if u.earliest_finish is not None:
            return u.earliest_finish
    for c in result.conflicts:
        if c.code in ("E1", "E2") and c.suggest and (
            c.suggest.startswith("EARLIEST:") or c.suggest.startswith("FEASIBLE:")
        ):
            return date.fromisoformat(c.suggest.split(":", 1)[1])
    return None
