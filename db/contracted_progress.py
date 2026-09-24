"""签约产品生产进度。一行一个订单产品，六档标签由现有事实算出。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.mis_orders import _sales_filter_for_role
from db.order_lines import lines_for_order
from db.prod_stats_seed import is_capacity_fixture_order
from db.tables import SoOrderRow

DONE = "done"
OPEN = "open"

_DEMO_PATH = Path(__file__).resolve().parents[1] / "seed" / "demo_data.json"


def _line_progress_facts(order_no: str, line_no: int) -> dict:
    if not _DEMO_PATH.is_file():
        return {}
    data = json.loads(_DEMO_PATH.read_text(encoding="utf-8"))
    block = (data.get("order_line_progress") or {}).get(order_no) or {}
    raw = block.get(str(line_no)) or block.get(line_no)
    return dict(raw) if isinstance(raw, dict) else {}


def _tag(label: str, tone: str) -> dict:
    return {"label": label, "tone": tone}


def contract_tag(has_contract: bool) -> dict:
    return _tag("已签订", DONE) if has_contract else _tag("未签订", OPEN)


def schedule_tag(phase: str) -> dict:
    phase = phase or "PENDING"
    if phase == "IN_PRODUCTION":
        return _tag("已排产", DONE)
    if phase == "IN_SCHEDULING":
        return _tag("排产中", OPEN)
    return _tag("待排产", OPEN)


def purchase_tag(purchased: bool) -> dict:
    return _tag("已采购", DONE) if purchased else _tag("未采购", OPEN)


def material_tag(*, purchased: bool, received_qty: float, need_qty: float) -> dict:
    if need_qty > 0 and received_qty >= need_qty:
        return _tag("已回料", DONE)
    if purchased and received_qty < need_qty:
        return _tag("在途中", OPEN)
    return _tag("未回料", OPEN)


def produce_tag(*, released: bool, reported_qty: float, plan_qty: float) -> dict:
    if not released:
        return _tag("未投产", OPEN)
    if plan_qty > 0 and reported_qty >= plan_qty:
        return _tag("已完工", DONE)
    return _tag("加工中", OPEN)


def inbound_tag(*, inbound_qty: float, sales_qty: float) -> dict:
    if inbound_qty <= 0:
        return _tag("未入库", OPEN)
    if sales_qty > 0 and inbound_qty >= sales_qty:
        return _tag("已入库", DONE)
    return _tag("部分入库", OPEN)


def non_negative(value: float) -> float:
    return value if value > 0 else 0.0


def progress_tags(
    *,
    has_contract: bool,
    schedule_phase: str,
    purchased: bool = False,
    received_qty: float = 0,
    need_qty: float = 0,
    reported_qty: float = 0,
    plan_qty: float = 0,
    inbound_qty: float = 0,
    sales_qty: float = 0,
) -> dict:
    phase = schedule_phase or "PENDING"
    released = phase == "IN_PRODUCTION"
    return {
        "contract": contract_tag(has_contract),
        "schedule": schedule_tag(phase),
        "purchase": purchase_tag(purchased),
        "material": material_tag(purchased=purchased, received_qty=received_qty, need_qty=need_qty),
        "produce": produce_tag(released=released, reported_qty=reported_qty, plan_qty=plan_qty),
        "inbound": inbound_tag(inbound_qty=inbound_qty, sales_qty=sales_qty),
    }


def list_contracted_progress(session: Session, *, role: str) -> list[dict]:
    rows = list(session.scalars(select(SoOrderRow).order_by(SoOrderRow.order_no)).all())
    rows = [
        r
        for r in rows
        if (r.order_status or "") != "CANCELLED"
        and not is_capacity_fixture_order(r.order_no, r.order_source)
    ]
    sales_as = _sales_filter_for_role(role)
    if role == "SALES" and sales_as:
        rows = [r for r in rows if (r.sales_name or r.owner_sales) == sales_as]
    show_cost = role in ("FIN", "GM")
    out: list[dict] = []
    for order in rows:
        phase = order.schedule_phase or "PENDING"
        has_contract = bool(order.contract_no)
        for line in lines_for_order(session, order.order_no):
            qty = float(line["qty"] or 0)
            price = float(line.get("unit_price") or 0)
            extras = _line_progress_facts(order.order_no, int(line["line_no"]))
            line_phase = str(extras.get("schedule_phase") or phase)
            reported = float(extras.get("reported_qty") or 0)
            inbound = float(extras.get("inbound_qty") or 0)
            purchased = bool(extras.get("purchased"))
            received = float(extras.get("received_qty") or 0)
            need = float(extras.get("need_qty") or 0)
            tags = progress_tags(
                has_contract=has_contract,
                schedule_phase=line_phase,
                purchased=purchased,
                received_qty=received,
                need_qty=need,
                sales_qty=qty,
                plan_qty=qty if line_phase == "IN_PRODUCTION" else (qty if reported > 0 else 0),
                reported_qty=reported,
                inbound_qty=inbound,
            )
            scheduled = qty if tags["schedule"]["label"] == "已排产" else 0.0
            item = {
                "order_no": order.order_no,
                "line_no": line["line_no"],
                "item_code": line["item_code"],
                "item_name": line.get("item_name") or line["item_code"],
                "spec": line.get("spec") or "",
                "sales_qty": qty,
                "unit": line.get("unit") or "",
                "unit_price": price,
                "line_amount": round(price * qty, 2),
                "suggest_price": None,
                "discount_label": "-",
                "suggest_amount": None,
                "shipped_qty": 0,
                "pending_ship_qty": non_negative(qty),
                "scheduled_qty": scheduled,
                "inbound_qty": 0,
                "pending_inbound_qty": non_negative(qty),
                "return_qty": 0,
                "tags": tags,
            }
            if show_cost:
                item["cost_amount"] = None
                item["cost_label"] = "尚无计划成本"
            out.append(item)
    return out
