"""交互式调整：工时重算、人手校验（纯函数）。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from engine.backward import apply_plan_dates
from engine.capacity import calendar_hours, hours_man, hours_wall
from engine.models import Dept, GroupCode, ScheduleInput, ScheduleResult, Wo, WoTask


def recalculate_task_hours(
    inp: ScheduleInput,
    wos: list[Wo],
    tasks: list[WoTask],
) -> list[WoTask]:
    """按当前 qty / crew / 组 SPH 重算墙钟与人·时。"""
    wo_by_no = {w.wo_no: w for w in wos}
    updated: list[WoTask] = []
    for task in tasks:
        wo = wo_by_no.get(task.wo_no)
        if wo is None:
            updated.append(task)
            continue
        sph = inp.sph_of(wo.item_code, task.group_code)
        converts = inp.converts_for(wo.item_code)
        wall = hours_wall(task.qty_board, sph, task.crew_plan, converts)
        man = hours_man(wall, task.crew_plan)
        updated.append(
            task.model_copy(
                update={
                    "hours_wall": wall,
                    "hours_man": man,
                }
            )
        )
    return updated


def sync_wos_plan_dates(wos: list[Wo], tasks: list[WoTask]) -> list[Wo]:
    """由任务日期回写工单 plan_start / plan_end。"""
    by_wo: dict[str, list[WoTask]] = defaultdict(list)
    for t in tasks:
        by_wo[t.wo_no].append(t)
    out: list[Wo] = []
    for wo in wos:
        batch = by_wo.get(wo.wo_no, [])
        if batch:
            out.append(apply_plan_dates(wo.model_copy(), batch))
        else:
            out.append(wo)
    return out


def headcount_warnings(
    inp: ScheduleInput,
    tasks: list[WoTask],
    *,
    only_cells: set[tuple[str, str, date]] | None = None,
) -> list[dict]:
    """工作中心×日人手与墙钟软提示（不阻断）。"""
    warnings: list[dict] = []
    by_cell: dict[tuple[str, str, date], list[WoTask]] = defaultdict(list)
    for t in tasks:
        by_cell[(t.dept.value, t.group_code.value, t.task_date)].append(t)

    for (dept_val, group_val, task_date), cell_tasks in by_cell.items():
        if only_cells is not None and (dept_val, group_val, task_date) not in only_cells:
            continue
        dept = Dept(dept_val)
        group_code = GroupCode(group_val)
        cal_row = next(
            (
                c
                for c in inp.calendar
                if c.dept == dept and c.group_code == group_code and c.work_date == task_date
            ),
            None,
        )
        headcount = cal_row.headcount if cal_row else 0
        limit_h = calendar_hours(inp.calendar, dept, group_code, task_date)
        wall_sum = sum(t.hours_wall for t in cell_tasks)
        crew_sum = sum(t.crew_plan for t in cell_tasks)
        max_crew = max(t.crew_plan for t in cell_tasks)
        wc = f"{dept_val}:{group_val}"

        for t in cell_tasks:
            if headcount and t.crew_plan > headcount:
                warnings.append(
                    {
                        "code": "CREW_OVER_HEAD",
                        "level": "RED",
                        "task_id": t.task_id,
                        "wo_no": t.wo_no,
                        "dept": dept_val,
                        "group_code": group_val,
                        "work_date": task_date.isoformat(),
                        "message": (
                            f"{wc} {task_date} 任务人力 {t.crew_plan} "
                            f"超过组在编 {headcount} 人"
                        ),
                    }
                )

        if headcount and crew_sum > headcount:
            warnings.append(
                {
                    "code": "CREW_SUM_OVER",
                    "level": "YELLOW",
                    "task_id": None,
                    "wo_no": None,
                    "dept": dept_val,
                    "group_code": group_val,
                    "work_date": task_date.isoformat(),
                    "message": (
                        f"{wc} {task_date} 当日任务人力合计 {crew_sum} "
                        f"超过组在编 {headcount} 人（并行上限）"
                    ),
                }
            )

        if wall_sum > limit_h and limit_h > 0:
            warnings.append(
                {
                    "code": "WALL_OVER_DAY",
                    "level": "YELLOW",
                    "task_id": None,
                    "wo_no": None,
                    "dept": dept_val,
                    "group_code": group_val,
                    "work_date": task_date.isoformat(),
                    "message": (
                        f"{wc} {task_date} 墙钟合计 {wall_sum}h "
                        f"超过日可用 {limit_h}h"
                    ),
                }
            )

        if headcount and max_crew <= headcount and crew_sum <= headcount:
            continue

    return warnings


def apply_interactive_patch(
    inp: ScheduleInput,
    wos: list[Wo],
    tasks: list[WoTask],
    warning_cells: set[tuple[str, str, date]] | None = None,
) -> tuple[ScheduleResult, list[dict]]:
    """预览：重算工时 + 人手警告。"""
    tasks2 = recalculate_task_hours(inp, wos, tasks)
    wos2 = sync_wos_plan_dates(wos, tasks2)
    warnings = headcount_warnings(inp, tasks2, only_cells=warning_cells)
    return ScheduleResult(wos=wos2, tasks=tasks2), warnings
