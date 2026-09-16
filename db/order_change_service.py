"""订单变更 + 影响清单（BR-27：仅审批流可改 due_date）。"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.interactive_preview import _order_impacts
from db.order_lifecycle import scheduling_pool_order_nos
from db.repositories import get_order, update_order_due_date_by_user
from db.snapshot import load_schedule_input
from db.tables import OrderChangeRequestRow
from engine.diff import diff
from engine.schedule import schedule


def _schedule_pool(session: Session, today: date, due_overrides: dict[str, date] | None = None):
    pool = scheduling_pool_order_nos(session)
    if not pool:
        pool = ["SO-001", "SO-002", "SO-003"]
    inp = load_schedule_input(session, today=today, order_nos=sorted(pool))
    if due_overrides:
        orders = []
        for o in inp.orders:
            if o.order_no in due_overrides:
                orders.append(o.model_copy(update={"due_date": due_overrides[o.order_no]}))
            else:
                orders.append(o)
        inp = inp.model_copy(update={"orders": orders})
    return schedule(inp)


def compute_due_change_impact(
    session: Session,
    *,
    order_no: str,
    new_due: date,
    today: date,
) -> dict:
    order = get_order(session, order_no)
    old_due = order.due_date
    baseline = _schedule_pool(session, today, None)
    proposed = _schedule_pool(session, today, {order_no: new_due})
    d = diff(baseline, proposed, today)
    impacts = _order_impacts(baseline, proposed, order_no)
    ripple_orders = [x for x in impacts if x["order_no"] != order_no]
    return {
        "order_no": order_no,
        "change_type": "DUE_DATE",
        "old_due": old_due.isoformat(),
        "new_due": new_due.isoformat(),
        "diff_summary": d.summary_text,
        "diff_entries": [e.model_dump(mode="json") for e in d.entries],
        "order_impacts": impacts,
        "ripple_count": len(ripple_orders),
        "conflicts": [c.model_dump(mode="json") for c in proposed.conflicts[:12]],
    }


def create_change_request(
    session: Session,
    *,
    order_no: str,
    new_due: date,
    requested_by: str,
    requested_role: str,
    today: date,
) -> OrderChangeRequestRow:
    order = get_order(session, order_no)
    impact = compute_due_change_impact(session, order_no=order_no, new_due=new_due, today=today)
    row = OrderChangeRequestRow(
        order_no=order_no,
        change_type="DUE_DATE",
        old_value_json=json.dumps({"due_date": order.due_date.isoformat()}, ensure_ascii=False),
        new_value_json=json.dumps({"due_date": new_due.isoformat()}, ensure_ascii=False),
        status="PENDING",
        requested_by=requested_by,
        requested_role=requested_role,
        impact_json=json.dumps(impact, ensure_ascii=False, default=str),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def approve_change_request(session: Session, *, request_id: int, approver_role: str) -> OrderChangeRequestRow:
    if approver_role not in ("PMC", "GM"):
        raise PermissionError("仅 PMC/总经理可批准交期变更")
    row = session.get(OrderChangeRequestRow, request_id)
    if row is None:
        raise KeyError(request_id)
    if row.status != "PENDING":
        raise ValueError("已处理")
    payload = json.loads(row.new_value_json)
    new_due = date.fromisoformat(payload["due_date"])
    update_order_due_date_by_user(session, row.order_no, new_due)
    row.status = "APPROVED"
    row.resolved_at = datetime.now(UTC)
    return row


def reject_change_request(session: Session, *, request_id: int, approver_role: str) -> OrderChangeRequestRow:
    if approver_role not in ("PMC", "GM"):
        raise PermissionError("仅 PMC/总经理可驳回")
    row = session.get(OrderChangeRequestRow, request_id)
    if row is None:
        raise KeyError(request_id)
    row.status = "REJECTED"
    row.resolved_at = datetime.now(UTC)
    return row


def list_change_requests(session: Session, limit: int = 50) -> list[dict]:
    rows = session.scalars(
        select(OrderChangeRequestRow).order_by(OrderChangeRequestRow.id.desc()).limit(limit)
    ).all()
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "order_no": r.order_no,
                "change_type": r.change_type,
                "status": r.status,
                "requested_by": r.requested_by,
                "requested_role": r.requested_role,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "impact": json.loads(r.impact_json or "{}"),
            }
        )
    return out
