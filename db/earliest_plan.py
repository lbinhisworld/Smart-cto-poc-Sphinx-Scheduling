"""交期排不下时的最快方案。只在内存里改锚试排，不落库、不改交期。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from db.bom_view import bom_explode
from db.plan_store import current_plan_version, load_schedule_result
from db.snapshot import header_order_no, load_schedule_input
from db.tables import SoOrderRow
from engine.schedule import schedule

TITLE = "提案 · 未改交期 · 未下发"


def build_earliest_plan(
    session: Session,
    *,
    order_no: str,
    today: date,
    run_id: str = "",
) -> dict:
    header = header_order_no(order_no)
    row = session.get(SoOrderRow, header)
    if row is None:
        raise KeyError(header)
    due = row.due_date
    version = current_plan_version(session)
    base = {
        "order_no": header,
        "run_id": run_id,
        "original_due": due.isoformat(),
        "plan_version": version,
        "title": TITLE,
    }
    if version <= 0:
        return {**base, "eligible": False, "reason": "请先倒排", "deliverable": False}

    result = load_schedule_result(session, version)
    wo_nos = {w.wo_no for w in result.wos if header_order_no(w.source_order_no) == header}
    if not wo_nos:
        return {**base, "eligible": False, "reason": "这张单不在当前计划里", "deliverable": False}

    dates: list[date] = []
    stuck = "未安置"
    for conflict in result.conflicts:
        if conflict.wo_no not in wo_nos or not conflict.suggest:
            continue
        if conflict.code == "E2":
            stuck = "半成品来不及"
        if conflict.suggest.startswith("EARLIEST:"):
            dates.append(date.fromisoformat(conflict.suggest.split(":", 1)[1]))
    if not dates:
        return {**base, "eligible": False, "reason": "交期本身够，不发给销售", "deliverable": False}
    anchor = max(dates)
    if anchor <= due:
        return {**base, "eligible": False, "reason": "交期本身够，不发给销售", "deliverable": False}

    inp = load_schedule_input(session, today=today, order_nos=[header])
    trial_orders = [
        o.model_copy(update={"due_date": anchor}) if header_order_no(o.order_no) == header else o
        for o in inp.orders
    ]
    trial = schedule(inp.model_copy(update={"orders": trial_orders}))
    own = [w for w in trial.wos if header_order_no(w.source_order_no) == header]
    own_nos = {w.wo_no for w in own}
    own_tasks = [t for t in trial.tasks if t.wo_no in own_nos]
    still = [u for u in trial.unplaced if u.wo_no in own_nos and u.remaining > 0]
    deliverable = not still
    days = sorted({t.task_date for t in own_tasks})
    wall = sum((t.hours_wall for t in own_tasks), start=Decimal(0))
    man = sum((t.hours_man for t in own_tasks), start=Decimal(0))
    picks = _pick_summary(session, row.item_code, row.qty_order, row.unit, today)
    day_count = len(days)
    sentences: list[str] = []
    if deliverable:
        material = "、".join(f"{p['name']} {p['gross_board']} 版" for p in picks[:3]) or "无下级子件"
        sentences = [
            f"建议交期不早于 {anchor.isoformat()}",
            f"要做 {day_count} 天",
            f"主要用料：{material}",
        ]
    note = "" if deliverable else "最快日试排仍未排完"
    reason = still[0].reason if still else ""
    return {
        **base,
        "eligible": True,
        "deliverable": deliverable,
        "reason": note or stuck,
        "stuck": stuck,
        "suggested_due": anchor.isoformat(),
        "still_unplaced": not deliverable,
        "still_reason": reason,
        "note": note,
        "day_count": day_count,
        "plan_start": days[0].isoformat() if days else None,
        "plan_end": days[-1].isoformat() if days else None,
        "tasks": [
            {
                "task_date": t.task_date.isoformat(),
                "group_code": t.group_code.value,
                "dept": t.dept.value,
                "qty_board": t.qty_board,
                "hours_wall": format(t.hours_wall, "f"),
                "hours_man": format(t.hours_man, "f"),
            }
            for t in own_tasks
        ],
        "hours_wall": format(wall.quantize(Decimal("0.01")), "f"),
        "hours_man": format(man.quantize(Decimal("0.01")), "f"),
        "pick_lines": picks,
        "sales_sentences": sentences,
    }


def _pick_summary(session: Session, item_code: str, qty, unit: str, today: date) -> list[dict]:
    from db.tables import MdItemRow

    exploded = bom_explode(session, item_code, Decimal(str(qty)), unit, today=today)
    if not exploded or not exploded.get("computable", True):
        return []

    lines = exploded.get("line_details") or []
    out = []
    for line in lines:
        code = line.get("component_item_code") or ""
        item = session.get(MdItemRow, code) if code else None
        out.append(
            {
                "component_item_code": code,
                "name": item.item_name if item else code,
                "gross_board": int(line.get("gross_board") or 0),
            }
        )
    if out:
        return out
    semi = exploded.get("semi") or {}
    if semi.get("semi_item_code"):
        return [
            {
                "component_item_code": semi["semi_item_code"],
                "name": semi.get("semi_item_code"),
                "gross_board": int(semi.get("gross_board") or 0),
            }
        ]
    return []
