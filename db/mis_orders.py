"""M3 销售订单列表（七巧风 MIS 视图）。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

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

    sales_as = _sales_filter_for_role(role)
    if role == "SALES" and sales_as:
        rows = [r for r in rows if (r.sales_name or r.owner_sales) == sales_as]

    if view == "pending_schedule":
        rows = [
            r
            for r in rows
            if (r.schedule_phase or "PENDING") == "IN_SCHEDULING"
            or (
                r.order_status == "CONFIRMED"
                and (r.schedule_phase or "PENDING") == "PENDING"
            )
        ]
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
            }
        )

    all_rows = list(session.scalars(select(SoOrderRow)).all())
    stats = {
        "total": len(all_rows),
        "pending_schedule": sum(
            1
            for r in all_rows
            if (r.schedule_phase or "") == "IN_SCHEDULING"
            or (
                r.order_status == "CONFIRMED"
                and (r.schedule_phase or "PENDING") == "PENDING"
            )
        ),
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
