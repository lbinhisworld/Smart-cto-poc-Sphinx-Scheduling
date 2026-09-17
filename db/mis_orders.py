"""M3 销售订单列表（七巧风 MIS 视图）。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.order_lines import lines_for_order, lines_summary
from db.tables import SoOrderRow

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "seed" / "demo_data.json"


def _sales_filter_for_role(role: str) -> str | None:
    if not DEMO_PATH.is_file():
        return None
    data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    return (data.get("sales_role_filter") or {}).get(role)


def list_mis_orders(
    session: Session,
    *,
    role: str,
    view: str,
    today: date,
) -> tuple[list[dict], dict]:
    q = select(SoOrderRow).order_by(SoOrderRow.due_date, SoOrderRow.order_no)
    rows = list(session.scalars(q).all())
    rows = [r for r in rows if (r.order_status or "") != "CANCELLED"]

    sales_as = _sales_filter_for_role(role)
    if role == "SALES" and sales_as:
        rows = [r for r in rows if (r.sales_name or r.owner_sales) == sales_as]

    if view == "pending":
        rows = [r for r in rows if (r.schedule_phase or "PENDING") == "PENDING"]
    elif view == "in_scheduling":
        rows = [r for r in rows if (r.schedule_phase or "") == "IN_SCHEDULING"]
    elif view == "in_production":
        rows = [r for r in rows if (r.schedule_phase or "") == "IN_PRODUCTION"]
    elif view == "pending_schedule":
        # 与「待排程」同口径：尚未加入排程池。进池后只出现在排程中。
        rows = [r for r in rows if (r.schedule_phase or "PENDING") == "PENDING"]
    elif view == "near_due":
        rows = [
            r
            for r in rows
            if (r.due_date - today).days <= 7 and r.order_status != "CLOSED"
        ]
    elif view == "low_kitting":
        rows = [r for r in rows if (r.kitting_rate_pct or 100) < 80]

    out: list[dict] = []
    for r in rows:
        remain = (r.due_date - today).days
        lines = lines_for_order(session, r.order_no)
        out.append(
            {
                "order_no": r.order_no,
                "customer": r.customer,
                "sales_name": r.sales_name or "",
                "item_code": r.item_code,
                "due_date": r.due_date.isoformat(),
                "remain_days": remain,
                "amount": float(r.amount),
                "kitting_rate_pct": r.kitting_rate_pct,
                "order_status": r.order_status or "CONFIRMED",
                "schedule_phase": r.schedule_phase or "PENDING",
                "line_count": len(lines),
                "lines_summary": lines_summary(lines),
            }
        )

    all_rows = [
        r
        for r in session.scalars(select(SoOrderRow)).all()
        if (r.order_status or "") != "CANCELLED"
    ]
    pending_n = sum(1 for r in all_rows if (r.schedule_phase or "PENDING") == "PENDING")
    in_sched_n = sum(1 for r in all_rows if (r.schedule_phase or "") == "IN_SCHEDULING")
    in_prod_n = sum(1 for r in all_rows if (r.schedule_phase or "") == "IN_PRODUCTION")
    stats = {
        "total": len(all_rows),
        "pending": pending_n,
        "in_scheduling": in_sched_n,
        "in_production": in_prod_n,
        "pending_schedule": pending_n,
        "avg_kitting": (
            round(sum(r.kitting_rate_pct or 0 for r in all_rows) / len(all_rows))
            if all_rows
            else 0
        ),
        "near_due": sum(
            1
            for r in all_rows
            if (r.due_date - today).days <= 7 and r.order_status != "CLOSED"
        ),
    }
    return out, stats
