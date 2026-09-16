"""CRM 合同、回款计划与登记。"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.tables import (
    CrmContractPaymentPlanRow,
    CrmContractRow,
    CrmCustomerRow,
    CrmPaymentReceiptRow,
    SoOrderRow,
)
from shared.contract_math import money, pending_amount, receipt_would_exceed


def next_contract_no(session: Session, *, today: date | None = None) -> str:
    anchor = today or date(2026, 9, 15)
    prefix = f"CT-{anchor.strftime('%Y%m')}-"
    rows = session.scalars(
        select(CrmContractRow.contract_no).where(CrmContractRow.contract_no.like(f"{prefix}%"))
    ).all()
    seq = 0
    for no in rows:
        tail = no[len(prefix) :]
        if tail.isdigit():
            seq = max(seq, int(tail))
    return f"{prefix}{seq + 1:04d}"


def _received_total(session: Session, contract_no: str) -> Decimal:
    rows = session.scalars(
        select(CrmPaymentReceiptRow).where(
            CrmPaymentReceiptRow.contract_no == contract_no,
            CrmPaymentReceiptRow.status == "CONFIRMED",
        )
    ).all()
    return sum((money(r.amount) for r in rows), Decimal("0"))


def _refresh_plan_statuses(session: Session, contract_no: str, *, today: date) -> None:
    contract = session.get(CrmContractRow, contract_no)
    if contract is None:
        return
    plans = session.scalars(
        select(CrmContractPaymentPlanRow)
        .where(CrmContractPaymentPlanRow.contract_no == contract_no)
        .order_by(CrmContractPaymentPlanRow.line_no)
    ).all()
    for p in plans:
        allocated = Decimal("0")
        if p.id:
            allocated = session.scalar(
                select(func.coalesce(func.sum(CrmPaymentReceiptRow.amount), 0)).where(
                    CrmPaymentReceiptRow.plan_id == p.id,
                    CrmPaymentReceiptRow.status == "CONFIRMED",
                )
            )
            allocated = money(allocated or 0)
        plan_amt = money(p.plan_amount)
        if allocated >= plan_amt:
            p.status = "PAID"
        elif allocated > 0:
            p.status = "PARTIAL"
        elif p.plan_date < today:
            p.status = "OVERDUE"
        else:
            p.status = "OPEN"
    session.flush()


def list_contracts(
    session: Session,
    *,
    customer_code: str | None = None,
    status: str | None = None,
    owner_filter: str | None = None,
) -> list[dict]:
    q = select(CrmContractRow).order_by(CrmContractRow.created_at.desc())
    rows = session.scalars(q).all()
    out: list[dict] = []
    for r in rows:
        if customer_code and r.customer_code != customer_code:
            continue
        if status and r.status != status:
            continue
        if owner_filter and r.owner_sales != owner_filter:
            continue
        received = _received_total(session, r.contract_no)
        amt = money(r.contract_amount)
        out.append(
            {
                "contract_no": r.contract_no,
                "customer_code": r.customer_code,
                "title": r.title,
                "status": r.status,
                "contract_amount": float(amt),
                "received_total": float(received),
                "pending_total": float(pending_amount(amt, received)),
                "signed_date": r.signed_date.isoformat() if r.signed_date else None,
                "owner_sales": r.owner_sales,
            }
        )
    return out


def contract_detail(session: Session, contract_no: str, *, today: date | None = None) -> dict | None:
    anchor = today or date(2026, 9, 15)
    r = session.get(CrmContractRow, contract_no)
    if r is None:
        return None
    _refresh_plan_statuses(session, contract_no, today=anchor)
    cust = session.get(CrmCustomerRow, r.customer_code)
    received = _received_total(session, contract_no)
    amt = money(r.contract_amount)
    plans = session.scalars(
        select(CrmContractPaymentPlanRow)
        .where(CrmContractPaymentPlanRow.contract_no == contract_no)
        .order_by(CrmContractPaymentPlanRow.line_no)
    ).all()
    receipts = session.scalars(
        select(CrmPaymentReceiptRow)
        .where(CrmPaymentReceiptRow.contract_no == contract_no)
        .order_by(CrmPaymentReceiptRow.receipt_date.desc())
    ).all()
    orders = session.scalars(
        select(SoOrderRow).where(SoOrderRow.contract_no == contract_no).order_by(SoOrderRow.due_date.desc())
    ).all()
    return {
        "contract_no": r.contract_no,
        "customer_code": r.customer_code,
        "customer_name": cust.name if cust else r.customer_code,
        "title": r.title,
        "status": r.status,
        "contract_amount": float(amt),
        "received_total": float(received),
        "pending_total": float(pending_amount(amt, received)),
        "signed_date": r.signed_date.isoformat() if r.signed_date else None,
        "owner_sales": r.owner_sales,
        "terms": json.loads(r.terms_json or "{}"),
        "plans": [
            {
                "id": p.id,
                "line_no": p.line_no,
                "milestone": p.milestone,
                "condition_type": p.condition_type,
                "condition_note": p.condition_note,
                "plan_date": p.plan_date.isoformat(),
                "plan_amount": float(money(p.plan_amount)),
                "status": p.status,
            }
            for p in plans
        ],
        "receipts": [
            {
                "id": rc.id,
                "plan_id": rc.plan_id,
                "receipt_date": rc.receipt_date.isoformat(),
                "amount": float(money(rc.amount)),
                "method": rc.method,
                "ref_no": rc.ref_no,
                "status": rc.status,
                "note": rc.note,
            }
            for rc in receipts
        ],
        "orders": [
            {
                "order_no": o.order_no,
                "item_code": o.item_code,
                "due_date": o.due_date.isoformat(),
                "amount": float(money(o.amount)),
                "order_status": o.order_status,
            }
            for o in orders
        ],
    }


def create_contract(
    session: Session,
    *,
    customer_code: str,
    title: str,
    contract_amount: Decimal,
    status: str,
    signed_date: date | None,
    owner_sales: str,
    terms: dict,
    plans: list[dict],
    opportunity_id: int | None = None,
    today: date | None = None,
) -> dict:
    anchor = today or date(2026, 9, 15)
    cust = session.get(CrmCustomerRow, customer_code)
    if cust is None:
        raise ValueError("客户不存在")
    if contract_amount <= 0:
        raise ValueError("合同金额须大于 0")
    plan_sum = sum(money(p.get("plan_amount", 0)) for p in plans)
    if plans and plan_sum != money(contract_amount):
        raise ValueError("回款计划合计须等于合同金额")
    now = datetime.now(UTC).replace(tzinfo=None)
    no = next_contract_no(session, today=anchor)
    session.add(
        CrmContractRow(
            contract_no=no,
            customer_code=customer_code,
            title=title,
            status=status,
            contract_amount=str(money(contract_amount)),
            signed_date=signed_date,
            owner_sales=owner_sales or cust.owner_sales,
            opportunity_id=opportunity_id,
            terms_json=json.dumps(terms or {}, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
    )
    for p in plans:
        session.add(
            CrmContractPaymentPlanRow(
                contract_no=no,
                line_no=int(p["line_no"]),
                milestone=str(p.get("milestone") or ""),
                condition_type=str(p.get("condition_type") or "CUSTOM"),
                condition_note=str(p.get("condition_note") or ""),
                plan_date=date.fromisoformat(p["plan_date"])
                if isinstance(p["plan_date"], str)
                else p["plan_date"],
                plan_amount=str(money(p["plan_amount"])),
                status="OPEN",
            )
        )
    session.flush()
    _refresh_plan_statuses(session, no, today=anchor)
    detail = contract_detail(session, no, today=anchor)
    assert detail is not None
    return detail


def add_receipt(
    session: Session,
    contract_no: str,
    *,
    receipt_date: date,
    amount: Decimal,
    method: str,
    ref_no: str,
    note: str,
    plan_id: int | None,
    today: date | None = None,
) -> dict:
    anchor = today or date(2026, 9, 15)
    contract = session.get(CrmContractRow, contract_no)
    if contract is None:
        raise KeyError(contract_no)
    amt = money(amount)
    if amt <= 0:
        raise ValueError("回款金额须大于 0")
    received = _received_total(session, contract_no)
    if receipt_would_exceed(money(contract.contract_amount), received, amt):
        raise ValueError("累计回款不能超过合同总额")
    if plan_id is not None:
        plan = session.get(CrmContractPaymentPlanRow, plan_id)
        if plan is None or plan.contract_no != contract_no:
            raise ValueError("无效回款计划行")
    session.add(
        CrmPaymentReceiptRow(
            contract_no=contract_no,
            plan_id=plan_id,
            receipt_date=receipt_date,
            amount=str(amt),
            method=method or "银行转账",
            ref_no=ref_no or "",
            status="CONFIRMED",
            note=note or "",
        )
    )
    session.flush()
    _refresh_plan_statuses(session, contract_no, today=anchor)
    detail = contract_detail(session, contract_no, today=anchor)
    assert detail is not None
    return detail


def validate_order_contract(
    session: Session,
    *,
    customer_code: str,
    contract_no: str,
) -> CrmContractRow:
    if not contract_no:
        raise ValueError("销售订单必须关联合同")
    row = session.get(CrmContractRow, contract_no)
    if row is None:
        raise ValueError("合同不存在")
    if row.customer_code != customer_code:
        raise ValueError("合同与客户不匹配")
    if row.status != "ACTIVE":
        raise ValueError("仅 ACTIVE 合同可下单")
    return row


def customer_payment_summary(session: Session, customer_code: str) -> dict:
    contracts = session.scalars(
        select(CrmContractRow).where(
            CrmContractRow.customer_code == customer_code,
            CrmContractRow.status.in_(("ACTIVE", "CLOSED")),
        )
    ).all()
    total_contract = Decimal("0")
    total_received = Decimal("0")
    for c in contracts:
        total_contract += money(c.contract_amount)
        total_received += _received_total(session, c.contract_no)
    return {
        "received": float(total_received),
        "pending": float(pending_amount(total_contract, total_received)),
        "contract_total": float(total_contract),
    }


def customer_metrics(session: Session, *, owner_filter: str | None = None) -> dict:
    customers = session.scalars(select(CrmCustomerRow).order_by(CrmCustomerRow.code)).all()
    channel: dict[str, int] = {}
    level: dict[str, int] = {}
    received_total = Decimal("0")
    pending_total = Decimal("0")
    count = 0
    for c in customers:
        if owner_filter and c.owner_sales != owner_filter:
            continue
        count += 1
        channel[c.channel_l1] = channel.get(c.channel_l1, 0) + 1
        lk = f"L{c.level}"
        level[lk] = level.get(lk, 0) + 1
        summary = customer_payment_summary(session, c.code)
        received_total += money(summary["received"])
        pending_total += money(summary["pending"])
    return {
        "customer_count": count,
        "channel_distribution": [{"label": k, "count": v} for k, v in sorted(channel.items())],
        "level_distribution": [{"label": k, "count": v} for k, v in sorted(level.items())],
        "received_total": float(received_total),
        "pending_total": float(pending_total),
    }


def list_overdue_payment_todos(session: Session, *, today: date) -> list[dict]:
    plans = session.scalars(select(CrmContractPaymentPlanRow)).all()
    todos: list[dict] = []
    seen: set[str] = set()
    for p in plans:
        if p.status not in ("OPEN", "PARTIAL", "OVERDUE"):
            continue
        if p.plan_date >= today:
            continue
        contract = session.get(CrmContractRow, p.contract_no)
        if contract is None or contract.status != "ACTIVE":
            continue
        key = p.contract_no
        if key in seen:
            continue
        seen.add(key)
        cust = session.get(CrmCustomerRow, contract.customer_code)
        todos.append(
            {
                "contract_no": contract.contract_no,
                "customer_code": contract.customer_code,
                "customer_name": cust.name if cust else contract.customer_code,
                "milestone": p.milestone,
                "plan_date": p.plan_date.isoformat(),
                "title": f"待回款 · {contract.contract_no}",
                "detail": f"{cust.name if cust else contract.customer_code} · 计划日 {p.plan_date}",
            }
        )
    return todos


def pick_active_contract(session: Session, customer_code: str) -> str | None:
    row = session.scalars(
        select(CrmContractRow)
        .where(CrmContractRow.customer_code == customer_code, CrmContractRow.status == "ACTIVE")
        .order_by(CrmContractRow.signed_date.desc())
    ).first()
    return row.contract_no if row else None
