"""计划版本 diff（§6.7）。"""

from __future__ import annotations

from datetime import date

from engine.models import ChangeType, DiffEntry, DiffResult, ScheduleResult, Wo


def _wo_map(result: ScheduleResult) -> dict[str, Wo]:
    return {wo.wo_no: wo for wo in result.wos}


def diff(base: ScheduleResult, new: ScheduleResult, today: date) -> DiffResult:
    """对比两版计划，生成 ADD/MOVE/DELAY/LATE/REMOVE 明细与汇总行。"""
    _ = today
    base_map = _wo_map(base)
    new_map = _wo_map(new)
    entries: list[DiffEntry] = []
    counts = {ChangeType.ADD: 0, ChangeType.MOVE: 0, ChangeType.DELAY: 0, ChangeType.LATE: 0, ChangeType.REMOVE: 0}

    for wo_no in sorted(set(base_map) | set(new_map)):
        b = base_map.get(wo_no)
        n = new_map.get(wo_no)
        if b is None and n is not None:
            entries.append(
                DiffEntry(change_type=ChangeType.ADD, wo_no=wo_no, message=f"新增工单 {wo_no}")
            )
            counts[ChangeType.ADD] += 1
            continue
        if b is not None and n is None:
            entries.append(
                DiffEntry(change_type=ChangeType.REMOVE, wo_no=wo_no, message=f"移除工单 {wo_no}")
            )
            counts[ChangeType.REMOVE] += 1
            continue
        assert b is not None and n is not None
        if b.plan_start != n.plan_start or b.plan_end != n.plan_end:
            if n.plan_end and n.due_date and n.plan_end > n.due_date:
                entries.append(
                    DiffEntry(
                        change_type=ChangeType.LATE,
                        wo_no=wo_no,
                        message=f"{wo_no} 超交期：完工 {n.plan_end} > 交期 {n.due_date}",
                    )
                )
                counts[ChangeType.LATE] += 1
            elif b.plan_end and n.plan_end and n.plan_end > b.plan_end:
                entries.append(
                    DiffEntry(
                        change_type=ChangeType.DELAY,
                        wo_no=wo_no,
                        message=f"{wo_no} 延后至 {n.plan_end}",
                    )
                )
                counts[ChangeType.DELAY] += 1
            else:
                entries.append(
                    DiffEntry(
                        change_type=ChangeType.MOVE,
                        wo_no=wo_no,
                        message=f"{wo_no} 开工 {b.plan_start} → {n.plan_start}",
                    )
                )
                counts[ChangeType.MOVE] += 1

    summary = (
        f"本次调整：新增 {counts[ChangeType.ADD]}、"
        f"移动 {counts[ChangeType.MOVE]}、"
        f"延后 {counts[ChangeType.DELAY]}、"
        f"超交期 {counts[ChangeType.LATE]}"
    )
    return DiffResult(entries=entries, summary_text=summary)
