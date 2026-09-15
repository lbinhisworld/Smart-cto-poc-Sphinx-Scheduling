"""齐套日计算（BR-39a）。"""

from __future__ import annotations

from datetime import date

from engine.models import ComponentRole, Conflict, ConflictLv, KitCheckResult, KitLineResult, ScheduleInput, ScheduleResult, Wo


def build_kit_checks(
    inp: ScheduleInput,
    result: ScheduleResult,
    lines_by_finished: dict[str, list[KitLineResult]],
) -> list[KitCheckResult]:
    wo_by_no = {w.wo_no: w for w in result.wos}
    semi_by_key: dict[tuple[str, int], Wo] = {}
    for w in result.wos:
        if w.wo_type.value == "SEMI" and w.bom_line_no is not None:
            semi_by_key[(w.source_order_no, w.bom_line_no)] = w

    checks: list[KitCheckResult] = []
    for fwo in result.wos:
        if fwo.wo_type.value != "FINISHED":
            continue
        kit_lines = lines_by_finished.get(fwo.wo_no, [])
        if not kit_lines:
            continue
        ready_candidates: list[date] = []
        for lr in kit_lines:
            if lr.component_role == ComponentRole.PURCHASED:
                if lr.shortage_board <= 0 and lr.ready_date:
                    ready_candidates.append(lr.ready_date)
                continue
            semi = semi_by_key.get((fwo.source_order_no, lr.line_no))
            if semi and semi.plan_end:
                lr.ready_date = semi.plan_end
                ready_candidates.append(semi.plan_end)
            elif lr.net_wo_board == 0 and lr.ready_date:
                ready_candidates.append(lr.ready_date)

        kit_ready = max(ready_candidates) if ready_candidates else None
        is_kitted = not any(ln.shortage_board > 0 for ln in kit_lines)
        if is_kitted and kit_ready and fwo.plan_start and fwo.plan_start < kit_ready:
            is_kitted = False
        fwo.kit_ready_date = kit_ready
        checks.append(
            KitCheckResult(
                order_no=fwo.source_order_no,
                finished_wo_no=fwo.wo_no,
                kit_ready_date=kit_ready,
                is_kitted=is_kitted,
                finished_plan_start=fwo.plan_start,
                lines=kit_lines,
            )
        )
    return checks


def detect_kit_conflicts(inp: ScheduleInput, result: ScheduleResult) -> list[Conflict]:
    out: list[Conflict] = []
    alloc_by_comp: dict[str, list] = {}
    for a in result.kit_allocations:
        alloc_by_comp.setdefault(a.component_item_code, []).append(a)

    for check in result.kit_checks:
        if not check.is_kitted and check.kit_ready_date and check.finished_plan_start:
            out.append(
                Conflict(
                    code="E9",
                    level=ConflictLv.YELLOW,
                    wo_no=check.finished_wo_no,
                    message=(
                        f"未齐套：计划开工 {check.finished_plan_start} 早于齐套日 {check.kit_ready_date}"
                    ),
                    suggest="CHECK_STOCK",
                )
            )
        for ln in check.lines:
            if ln.shortage_board > 0:
                out.append(
                    Conflict(
                        code="E9",
                        level=ConflictLv.YELLOW,
                        wo_no=check.finished_wo_no,
                        message=f"缺料 {ln.component_item_code} 缺 {ln.shortage_board} 版",
                        suggest="CHECK_STOCK",
                    )
                )

    for comp, allocs in alloc_by_comp.items():
        if len(allocs) > 1:
            orders = ", ".join(sorted({a.order_no for a in allocs}))
            total = sum(a.qty_board for a in allocs)
            out.append(
                Conflict(
                    code="E10",
                    level=ConflictLv.GREY,
                    message=f"共享库存 {comp}：{orders} 合计占用 {total} 版（按排产顺序扣减）",
                    suggest="REVIEW_SEQUENCE",
                )
            )
    return out
