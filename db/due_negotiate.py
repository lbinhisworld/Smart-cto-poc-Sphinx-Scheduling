"""PMC 发起交期协商：口径卡 → 销售提案 → PMC 改锚。禁止销售写 due_date。"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.order_change_service import compute_due_change_impact
from db.repositories import get_order, update_order_due_date_by_user
from db.tables import OrderChangeRequestRow, SoOrderDueEventRow


def classify_due_gap(old_due: date, suggested_due: date) -> str:
    """最快可完成日晚于客户交期才叫交期不够，才值得找销售。"""
    return "LATE" if suggested_due > old_due else "FEASIBLE"


def render_brief_text(
    *,
    order_no: str,
    customer: str,
    sales_name: str,
    item_code: str,
    old_due: date,
    suggested_due: date,
    reason: str,
) -> str:
    old_s = f"{old_due.month}/{old_due.day}"
    new_s = f"{suggested_due.month}/{suggested_due.day}"
    who = f"{customer}（{sales_name}）" if sales_name else customer
    if classify_due_gap(old_due, suggested_due) == "FEASIBLE":
        return (
            f"{order_no} {who} {item_code}，客户要 {old_s}。"
            f"系统物理最快 {new_s}，早于或不晚于客户交期，交期本身够，不必改客户交期。"
            f"红灯是倒排贴着 {old_s} 往回填时{reason}，不是客户要得太早。"
            f"请在排程侧把开工往前提或加班/加人，不要找销售改交期。"
        )
    return (
        f"我按如下口径回复销售：\n"
        f"{order_no} {who} {item_code}，客户要 {old_s}。"
        f"半成品库存不够，必须开生产工单补齐缺口。"
        f"按倒排试排后仍无法满足 {old_s} 交付，建议交付不早于 {new_s}。"
        f"未确认前计划仍按 {old_s} 挂红，不改客户交期。"
    )


def _add_event(
    session: Session,
    *,
    order_no: str,
    event_type: str,
    actor_role: str,
    payload: dict,
    run_id: str = "",
    change_request_id: int | None = None,
) -> SoOrderDueEventRow:
    row = SoOrderDueEventRow(
        order_no=order_no,
        event_type=event_type,
        actor_role=actor_role,
        payload_json=json.dumps(payload, ensure_ascii=False, default=str),
        run_id=run_id or "",
        change_request_id=change_request_id,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def preview_brief(
    session: Session,
    *,
    order_no: str,
    suggested_due: date,
    conflict_code: str,
    reason: str,
) -> dict:
    order = get_order(session, order_no)
    gap = classify_due_gap(order.due_date, suggested_due)
    text = render_brief_text(
        order_no=order.order_no,
        customer=order.customer,
        sales_name=order.sales_name or "",
        item_code=order.item_code,
        old_due=order.due_date,
        suggested_due=suggested_due,
        reason=reason or ("半成品来不及" if conflict_code == "E2" else "未在最早可排日前安置完"),
    )
    return {
        "order_no": order.order_no,
        "customer": order.customer,
        "sales_name": order.sales_name or "",
        "item_code": order.item_code,
        "old_due": order.due_date.isoformat(),
        "suggested_due": suggested_due.isoformat(),
        "conflict_code": conflict_code,
        "reason": reason,
        "brief_text": text,
        "due_gap": gap,
        "can_negotiate": gap == "LATE",
    }


def send_sales_brief(
    session: Session,
    *,
    order_no: str,
    suggested_due: date,
    conflict_code: str,
    reason: str,
    actor: str,
    role: str,
    run_id: str = "",
    brief_text: str | None = None,
) -> OrderChangeRequestRow:
    if role not in ("PMC", "GM"):
        raise PermissionError("仅 PMC/总经理可发出协商口径")
    order = get_order(session, order_no)
    if classify_due_gap(order.due_date, suggested_due) != "LATE":
        raise ValueError("系统最快不晚于客户交期，不必找销售改交期")
    due_before = order.due_date
    reason_text = reason or ("半成品来不及" if conflict_code == "E2" else "未在最早可排日前安置完")
    text = brief_text or render_brief_text(
        order_no=order.order_no,
        customer=order.customer,
        sales_name=order.sales_name or "",
        item_code=order.item_code,
        old_due=order.due_date,
        suggested_due=suggested_due,
        reason=reason_text,
    )
    row = OrderChangeRequestRow(
        order_no=order_no,
        change_type="DUE_DATE",
        source="SCHEDULING_CONFLICT",
        old_value_json=json.dumps({"due_date": order.due_date.isoformat()}, ensure_ascii=False),
        new_value_json=json.dumps({"due_date": suggested_due.isoformat()}, ensure_ascii=False),
        status="PENDING_SALES",
        requested_by=actor,
        requested_role=role,
        impact_json="{}",
        created_at=datetime.now(UTC),
        suggested_due=suggested_due,
        brief_text=text,
        run_id=run_id or "",
    )
    session.add(row)
    session.flush()
    _add_event(
        session,
        order_no=order_no,
        event_type="CONFLICT_FOUND",
        actor_role=role,
        payload={
            "conflict_code": conflict_code,
            "reason": reason_text,
            "suggested_due": suggested_due.isoformat(),
        },
        run_id=run_id or "",
        change_request_id=row.id,
    )
    _add_event(
        session,
        order_no=order_no,
        event_type="SALES_BRIEF_SENT",
        actor_role=role,
        payload={"brief_text": text, "suggested_due": suggested_due.isoformat()},
        run_id=run_id or "",
        change_request_id=row.id,
    )
    if order.due_date != due_before:
        raise RuntimeError("禁止写回订单交期（BR-27）")
    return row


def sales_reply_due(
    session: Session,
    *,
    request_id: int,
    proposed_due: date,
    actor: str,
    role: str,
    note: str = "",
) -> OrderChangeRequestRow:
    if role not in ("SALES", "SALES_MGR", "GM"):
        raise PermissionError("仅销售可回客户确认日")
    row = session.get(OrderChangeRequestRow, request_id)
    if row is None:
        raise KeyError(request_id)
    if row.source != "SCHEDULING_CONFLICT" or row.status != "PENDING_SALES":
        raise ValueError("当前状态不可回确认日")
    order = get_order(session, row.order_no)
    due_before = order.due_date
    row.sales_proposed_due = proposed_due
    row.status = "SALES_REPLIED"
    row.new_value_json = json.dumps({"due_date": proposed_due.isoformat()}, ensure_ascii=False)
    _add_event(
        session,
        order_no=row.order_no,
        event_type="SALES_REPLIED",
        actor_role=role,
        payload={
            "proposed_due": proposed_due.isoformat(),
            "note": note,
            "actor": actor,
        },
        run_id=row.run_id,
        change_request_id=row.id,
    )
    if order.due_date != due_before:
        raise RuntimeError("禁止写回订单交期（BR-27）")
    return row


def apply_negotiated_due(
    session: Session,
    *,
    request_id: int,
    role: str,
    today: date,
) -> OrderChangeRequestRow:
    if role not in ("PMC", "GM"):
        raise PermissionError("仅 PMC/总经理可改交期锚")
    row = session.get(OrderChangeRequestRow, request_id)
    if row is None:
        raise KeyError(request_id)
    if row.source != "SCHEDULING_CONFLICT" or row.status != "SALES_REPLIED":
        raise ValueError("需等销售回确认日后再改锚")
    new_due = row.sales_proposed_due
    if new_due is None:
        raise ValueError("缺少销售确认日")
    order = get_order(session, row.order_no)
    old_due = order.due_date
    impact = compute_due_change_impact(session, order_no=row.order_no, new_due=new_due, today=today)
    row.impact_json = json.dumps(impact, ensure_ascii=False, default=str)
    update_order_due_date_by_user(session, row.order_no, new_due)
    row.status = "APPROVED"
    row.resolved_at = datetime.now(UTC)
    _add_event(
        session,
        order_no=row.order_no,
        event_type="DUE_APPLIED",
        actor_role=role,
        payload={"old_due": old_due.isoformat(), "new_due": new_due.isoformat()},
        run_id=row.run_id,
        change_request_id=row.id,
    )
    return row


def list_due_events(session: Session, order_no: str) -> list[dict]:
    rows = session.scalars(
        select(SoOrderDueEventRow)
        .where(SoOrderDueEventRow.order_no == order_no)
        .order_by(SoOrderDueEventRow.id.asc())
    ).all()
    return [
        {
            "id": r.id,
            "order_no": r.order_no,
            "event_type": r.event_type,
            "actor_role": r.actor_role,
            "payload": json.loads(r.payload_json or "{}"),
            "run_id": r.run_id,
            "change_request_id": r.change_request_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def list_open_negotiations(session: Session, *, order_no: str | None = None) -> list[dict]:
    q = select(OrderChangeRequestRow).where(
        OrderChangeRequestRow.source == "SCHEDULING_CONFLICT",
        OrderChangeRequestRow.status.in_(("PENDING_SALES", "SALES_REPLIED")),
    )
    if order_no:
        q = q.where(OrderChangeRequestRow.order_no == order_no)
    rows = session.scalars(q.order_by(OrderChangeRequestRow.id.desc())).all()
    return [_negotiate_dict(r) for r in rows]


def get_negotiate(session: Session, request_id: int) -> dict | None:
    row = session.get(OrderChangeRequestRow, request_id)
    if row is None:
        return None
    return _negotiate_dict(row)


def _negotiate_dict(r: OrderChangeRequestRow) -> dict:
    return {
        "id": r.id,
        "order_no": r.order_no,
        "status": r.status,
        "source": r.source,
        "suggested_due": r.suggested_due.isoformat() if r.suggested_due else None,
        "sales_proposed_due": r.sales_proposed_due.isoformat() if r.sales_proposed_due else None,
        "brief_text": r.brief_text,
        "run_id": r.run_id,
        "impact": json.loads(r.impact_json or "{}"),
    }


def pending_sales_todos(session: Session) -> list[OrderChangeRequestRow]:
    return list(
        session.scalars(
            select(OrderChangeRequestRow)
            .where(OrderChangeRequestRow.source == "SCHEDULING_CONFLICT")
            .where(OrderChangeRequestRow.status == "PENDING_SALES")
            .order_by(OrderChangeRequestRow.id.desc())
            .limit(20)
        ).all()
    )


def pending_pmc_apply(session: Session) -> list[OrderChangeRequestRow]:
    return list(
        session.scalars(
            select(OrderChangeRequestRow)
            .where(OrderChangeRequestRow.source == "SCHEDULING_CONFLICT")
            .where(OrderChangeRequestRow.status == "SALES_REPLIED")
            .order_by(OrderChangeRequestRow.id.desc())
            .limit(20)
        ).all()
    )

