"""订单六层拆解（POC 简化：订单→明细→工单→任务）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.bom_view import bom_explode
from db.order_kitting import refresh_order_kitting
from db.plan_store import current_plan_version, load_schedule_result
from db.tables import SoOrderRow, WoRow, WoTaskRow


def order_breakdown(session: Session, order_no: str, *, today: date) -> dict | None:
    row = session.get(SoOrderRow, order_no)
    if row is None:
        return None

    kit = refresh_order_kitting(session, order_no, today=today)
    explode = bom_explode(
        session,
        row.item_code,
        Decimal(str(row.qty_order)),
        row.unit,
        today=today,
    )

    ver = current_plan_version(session)
    wos: list[dict] = []
    tasks: list[dict] = []
    if ver is not None:
        result = load_schedule_result(session, ver)
        if result is not None:
            for wo in result.wos:
                if wo.source_order_no != order_no:
                    continue
                wos.append(
                    {
                        "wo_no": wo.wo_no,
                        "wo_type": wo.wo_type.value,
                        "item_code": wo.item_code,
                        "qty_board_plan": wo.qty_board_plan,
                        "plan_start": wo.plan_start.isoformat() if wo.plan_start else None,
                        "plan_end": wo.plan_end.isoformat() if wo.plan_end else None,
                    }
                )
            wo_nos = {w["wo_no"] for w in wos}
            for t in result.tasks:
                if t.wo_no in wo_nos:
                    tasks.append(
                        {
                            "task_id": t.task_id,
                            "wo_no": t.wo_no,
                            "group_code": t.group_code.value,
                            "task_date": t.task_date.isoformat(),
                            "qty_board": t.qty_board,
                        }
                    )

    if not wos and ver is not None:
        for r in session.scalars(
            select(WoRow).where(WoRow.source_order_no == order_no, WoRow.plan_version == ver)
        ):
            wos.append(
                {
                    "wo_no": r.wo_no,
                    "wo_type": r.wo_type,
                    "item_code": r.item_code,
                    "qty_board_plan": r.qty_board_plan,
                    "plan_start": r.plan_start.isoformat() if r.plan_start else None,
                    "plan_end": r.plan_end.isoformat() if r.plan_end else None,
                }
            )
        wo_nos = {w["wo_no"] for w in wos}
        for r in session.scalars(select(WoTaskRow).where(WoTaskRow.plan_version == ver)):
            if r.wo_no in wo_nos:
                tasks.append(
                    {
                        "task_id": r.task_id,
                        "wo_no": r.wo_no,
                        "group_code": r.group_code,
                        "task_date": r.task_date.isoformat(),
                        "qty_board": r.qty_board,
                    }
                )

    return {
        "order": {
            "order_no": row.order_no,
            "customer": row.customer,
            "item_code": row.item_code,
            "qty_order": float(row.qty_order),
            "unit": row.unit,
            "due_date": row.due_date.isoformat(),
            "order_source": row.order_source,
            "schedule_phase": row.schedule_phase,
            "kitting_rate_pct": row.kitting_rate_pct,
        },
        "kitting": kit,
        "mrp_explode": explode,
        "work_orders": wos,
        "tasks": tasks,
    }
