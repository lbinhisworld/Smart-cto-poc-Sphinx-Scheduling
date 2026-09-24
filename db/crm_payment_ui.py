"""回款计划 · 与合同计划同一批行，行级实际与状态。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.contract_queries import contract_detail, money
from db.mis_orders import _sales_filter_for_role
from db.prod_stats_seed import is_capacity_fixture_order
from db.tables import CrmContractPaymentPlanRow, CrmPaymentReceiptRow, SoOrderRow

DEMO_TODAY = date(2026, 9, 15)

STATUS_LABEL = {
    "OPEN": "未回款",
    "PARTIAL": "部分回款",
    "PAID": "全部回款",
    "OVERDUE": "逾期未回",
}


def _plan_actuals(session: Session, plan_id: int) -> tuple[float, str | None, list[str]]:
    rows = session.scalars(
        select(CrmPaymentReceiptRow).where(
            CrmPaymentReceiptRow.plan_id == plan_id,
            CrmPaymentReceiptRow.status == "CONFIRMED",
        )
    ).all()
    total = sum(float(money(r.amount)) for r in rows)
    last_date: str | None = None
    refs: list[str] = []
    for r in rows:
        refs.append(r.ref_no or "")
        d = r.receipt_date.isoformat()
        if last_date is None or d > last_date:
            last_date = d
    return total, last_date, refs


def payment_plans_for_order(session: Session, order_no: str, *, today: date | None = None) -> list[dict]:
    order = session.get(SoOrderRow, order_no)
    if order is None:
        return []
    contract_no = order.contract_no
    if not contract_no:
        return []
    detail = contract_detail(session, contract_no, today=today or DEMO_TODAY)
    if not detail:
        return []
    out: list[dict] = []
    for p in detail.get("plans") or []:
        pid = p.get("id")
        actual_amt = 0.0
        actual_date = None
        kingdee_refs: list[str] = []
        if pid:
            actual_amt, actual_date, kingdee_refs = _plan_actuals(session, pid)
        st = p.get("status") or "OPEN"
        out.append(
            {
                "order_no": order_no,
                "contract_no": contract_no,
                "line_no": p.get("line_no"),
                "milestone": p.get("milestone"),
                "plan_amount": p.get("plan_amount"),
                "condition_note": p.get("condition_note"),
                "plan_date": p.get("plan_date"),
                "actual_amount": actual_amt,
                "actual_date": actual_date,
                "status_code": st,
                "status_label": STATUS_LABEL.get(st, st),
                "kingdee_refs": [r for r in kingdee_refs if r],
                "source": "合同计划",
            }
        )
    return out


def list_payment_plan_menu(
    session: Session,
    *,
    role: str,
    actor: str,
    order_no: str | None = None,
    today: date | None = None,
) -> list[dict]:
    anchor = today or DEMO_TODAY
    q = select(SoOrderRow).order_by(SoOrderRow.order_no)
    rows = session.scalars(q).all()
    sales = _sales_filter_for_role(role)
    out: list[dict] = []
    for order in rows:
        if is_capacity_fixture_order(order.order_no, order.order_source):
            continue
        if order_no and order.order_no != order_no:
            continue
        if role == "SALES" and sales and (order.sales_name or order.owner_sales) != sales:
            continue
        if not order.contract_no:
            continue
        for plan in payment_plans_for_order(session, order.order_no, today=anchor):
            plan["customer"] = order.customer
            plan["sales_name"] = order.sales_name or order.owner_sales
            out.append(plan)
    return out
