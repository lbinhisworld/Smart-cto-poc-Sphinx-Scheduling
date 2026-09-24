"""领料只读表。不改《组排程》列，不扣库存，不写交期。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.dispatch_export import _finished_components, group_label
from db.plan_facts import issue_progress, split_gross
from db.plan_store import current_plan_version
from db.stock_repository import stock_snapshot
from db.tables import InvIssueRow, SoOrderRow, WoRow, WoTaskRow


def build_pick_list(
    session: Session,
    *,
    group: str | None = None,
    dept: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    version = current_plan_version(session)
    if version <= 0:
        return []
    tasks = list(
        session.scalars(
            select(WoTaskRow)
            .where(WoTaskRow.plan_version == version)
            .order_by(WoTaskRow.task_date, WoTaskRow.seq, WoTaskRow.task_id)
        ).all()
    )
    wos = {
        w.wo_no: w
        for w in session.scalars(select(WoRow).where(WoRow.plan_version == version)).all()
    }
    orders = {
        o.order_no: o
        for o in session.scalars(
            select(SoOrderRow).where(
                SoOrderRow.order_no.in_({w.source_order_no.split("#L")[0] for w in wos.values()} or {"-"})
            )
        ).all()
    }
    issues = list(session.scalars(select(InvIssueRow)).all())
    issued_by: dict[tuple[str, date], int] = defaultdict(int)
    issued_all: dict[str, int] = defaultdict(int)
    for row in issues:
        issued_by[(row.item_code, row.work_date)] += int(row.qty_board)
        issued_all[row.item_code] += int(row.qty_board)
    stock = {code: int(qty) for code, qty in stock_snapshot(session).items()}

    tasks_by_wo: dict[str, list[WoTaskRow]] = defaultdict(list)
    for task in tasks:
        wo = wos.get(task.wo_no)
        if wo is None or wo.wo_type != "FINISHED":
            continue
        tasks_by_wo[task.wo_no].append(task)

    out: list[dict] = []
    for wo_no, wo_tasks in tasks_by_wo.items():
        wo = wos[wo_no]
        wo_tasks = sorted(wo_tasks, key=lambda t: (t.task_date, t.seq, t.task_id))
        day_qtys = [int(t.qty_board) for t in wo_tasks]
        plan_qty = int(wo.qty_board_plan)
        reported = any(t.qty_actual is not None for t in wo_tasks)
        components = _finished_components(session, wo, orders)
        for comp in components:
            code = comp.get("code") or ""
            gross = int(comp.get("gross") or 0)
            parts = split_gross(gross, day_qtys, plan_qty) if day_qtys else []
            for task, day_qty in zip(wo_tasks, parts):
                if group and task.group_code != group and group not in group_label(task.dept or wo.dept, task.group_code):
                    continue
                if dept and (task.dept or wo.dept) != dept:
                    continue
                if date_from and task.task_date < date_from:
                    continue
                if date_to and task.task_date > date_to:
                    continue
                today_issue = issued_by.get((code, task.task_date))
                has_issue = bool(code) and (issued_all.get(code, 0) > 0 or today_issue is not None)
                if has_issue:
                    progress = issue_progress(
                        gross=gross,
                        issued=issued_all.get(code, 0),
                        today_issued=today_issue or 0,
                    )
                elif reported:
                    issued_from_report = sum(
                        part
                        for other, part in zip(wo_tasks, parts)
                        if other.qty_actual is not None
                    )
                    progress = issue_progress(
                        gross=gross,
                        issued=issued_from_report,
                        today_issued=day_qty if task.qty_actual is not None else 0,
                    )
                else:
                    progress = issue_progress(gross=gross, issued=None, today_issued=None)
                out.append(
                    {
                        "work_date": task.task_date.isoformat(),
                        "group": group_label(task.dept or wo.dept, task.group_code),
                        "item_code": wo.item_code,
                        "seq": task.seq,
                        "component_code": code,
                        "component_name": comp.get("name") or "无下级子件",
                        "role": comp.get("role") or "",
                        "day_qty": day_qty,
                        "gross_board": gross,
                        "issued": progress["issued"],
                        "pending": progress["pending"],
                        "this_time": progress["this_time"],
                        "stock_board": stock.get(code) if code else None,
                        "demand_board": gross,
                        "wo_no": wo.wo_no,
                    }
                )
    out.sort(key=lambda row: (row["work_date"], row["group"], row["seq"], row["component_code"]))
    return out
