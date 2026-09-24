"""销售订单 360 · 回款 / 开票 / 生产 / 发货。"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.contract_queries import contract_detail
from db.contracted_progress import non_negative, progress_tags
from db.crm_payment_ui import payment_plans_for_order
from db.order_lines import lines_for_order
from db.tables import CrmContractRow, CrmCustomerRow, CrmOpportunityRow, CrmQuoteRow, SoOrderRow

DEMO_TODAY = __import__("datetime").date(2026, 9, 15)


def _discount_label(unit_price: float, suggest: float | None) -> str:
    if not suggest or suggest <= 0:
        return "-"
    pct = round(100 * unit_price / suggest, 1)
    return f"{pct}%"


def order_360(session: Session, order_no: str, *, today=None) -> dict | None:
    anchor = today or DEMO_TODAY
    order = session.get(SoOrderRow, order_no)
    if order is None:
        return None
    contract_no = order.contract_no
    if not contract_no:
        for c in session.scalars(
            select(CrmContractRow).where(CrmContractRow.customer_code == order.customer_code)
        ).all():
            if c.status == "ACTIVE":
                contract_no = c.contract_no
                break
    quote = session.get(CrmQuoteRow, order.quote_no) if order.quote_no else None
    cust = session.get(CrmCustomerRow, order.customer_code) if order.customer_code else None
    cf = json.loads(cust.custom_fields_json or "{}") if cust else {}
    opp_name = None
    if quote and quote.opportunity_id:
        opp = session.get(CrmOpportunityRow, quote.opportunity_id)
        opp_name = opp.name if opp else None
    payment_plans = payment_plans_for_order(session, order_no, today=anchor)
    invoices: list[dict] = []
    if contract_no:
        detail = contract_detail(session, contract_no, today=anchor)
        if detail:
            terms = detail.get("terms") or {}
            invoices = terms.get("kingdee_invoices") or []
            if not invoices:
                invoices = [
                    {
                        "invoice_date": "2026-09-10",
                        "invoice_type": "增值税专用发票",
                        "title": cust.name if cust else order.customer,
                        "tax_id": terms.get("tax_id") or "91310000MA1XXXXXX",
                        "bank": terms.get("bank") or "—",
                        "bank_account": terms.get("bank_account") or "—",
                        "invoice_no": f"INV-{contract_no}",
                        "source": "金蝶只读",
                    }
                ]
    phase = order.schedule_phase or "PENDING"
    has_contract = bool(contract_no)
    product_lines: list[dict] = []
    quote_lines: dict = {}
    if quote and quote.lines_json:
        try:
            for ln in json.loads(quote.lines_json):
                quote_lines[ln.get("item_code") or ln.get("item_name") or ""] = ln
        except json.JSONDecodeError:
            quote_lines = {}
    for ol in lines_for_order(session, order_no):
        qty = float(ol.get("qty") or 0)
        price = float(ol.get("unit_price") or 0)
        ql = quote_lines.get(ol.get("item_code")) or {}
        suggest = float(ql.get("unit_price_tax_in") or ql.get("unit_price") or 0) or None
        tags = progress_tags(
            has_contract=has_contract,
            schedule_phase=phase,
            plan_qty=qty if phase == "IN_PRODUCTION" else 0,
            sales_qty=qty,
        )
        scheduled = qty if tags["schedule"]["label"] == "已排产" else 0.0
        product_lines.append(
            {
                "line_no": ol["line_no"],
                "item_code": ol.get("item_code"),
                "item_name": ol.get("item_name") or ol.get("item_code"),
                "spec": ol.get("spec") or "",
                "item_type": ol.get("category") or "成品",
                "qty": qty,
                "unit": ol.get("unit") or "",
                "unit_price": price,
                "suggest_price": suggest,
                "discount_label": _discount_label(price, suggest),
                "line_amount": round(price * qty, 2),
                "tags": tags,
                "scheduled_qty": scheduled,
                "shipped_qty": 0,
                "pending_ship_qty": non_negative(qty),
            }
        )
    if not product_lines:
        qty = float(order.qty_order or 0)
        tags = progress_tags(has_contract=has_contract, schedule_phase=phase, plan_qty=qty, sales_qty=qty)
        product_lines.append(
            {
                "line_no": 1,
                "item_code": order.item_code,
                "item_name": order.item_code,
                "spec": "",
                "item_type": "成品",
                "qty": qty,
                "unit": order.unit,
                "unit_price": float(order.amount) / qty if qty else float(order.amount),
                "suggest_price": None,
                "discount_label": "-",
                "line_amount": float(order.amount),
                "tags": tags,
                "scheduled_qty": qty if phase == "IN_PRODUCTION" else 0,
                "shipped_qty": 0,
                "pending_ship_qty": non_negative(qty),
            }
        )
    ship_qty = 0
    shipments = [
        {
            "ship_date": None,
            "qty": ship_qty,
            "status": "未发货",
            "pending_qty": non_negative(sum(p["qty"] for p in product_lines) - ship_qty),
            "note": "金蝶同步只读；无记录即为未发货",
            "source": "金蝶只读",
        }
    ]
    tax_rate = float(quote.tax_rate) if quote and quote.tax_rate is not None else 0.13
    return {
        "order_no": order_no,
        "header": {
            "order_no": order_no,
            "customer": order.customer,
            "customer_code": order.customer_code,
            "sales_name": order.sales_name or order.owner_sales,
            "amount": float(order.amount),
            "quote_no": order.quote_no,
            "quote_title": order.quote_no,
            "opportunity_name": opp_name,
            "contract_no": contract_no,
            "due_date": order.due_date.isoformat(),
            "order_status": order.order_status,
            "schedule_phase": phase,
            "tax_included": True,
            "tax_rate": tax_rate,
            "region": cf.get("region") or cf.get("address_region") or "",
        },
        "customer": order.customer,
        "contract_no": contract_no,
        "product_lines": product_lines,
        "production_lines": product_lines,
        "payment_plans": payment_plans,
        "payments": payment_plans,
        "invoices": invoices,
        "shipments": shipments,
        "tabs": ["回款信息", "开票记录", "生产记录", "发货记录"],
    }
