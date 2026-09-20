"""C 链路：计划人工成本按量产成品品项汇总。打样/研发不进品项。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.labor_cost_queries import _rate_for_group
from db.plan_store import current_plan_version
from db.tables import CrmQuoteRow, SoOrderRow, WoRow, WoTaskRow
from shared.labor_math import decimal_hours, labor_cost

SAMPLE_COST_SOURCES = frozenset({"SAMPLE", "RND", "RD", "R&D", "SAMPLING"})
MASS_COST_NOTE = "量产成品人·时×标准单价；打样/研发工时已剔除，不摊进品项"


def header_order_no(order_no: str) -> str:
    return (order_no or "").split("#", 1)[0]


def is_sample_cost_source(order_source: str | None) -> bool:
    return (order_source or "").upper() in SAMPLE_COST_SOURCES


def quote_sample_order_nos(session: Session) -> set[str]:
    rows = session.execute(
        select(CrmQuoteRow.order_no).where(
            CrmQuoteRow.sample_code.is_not(None),
            CrmQuoteRow.sample_code != "",
            CrmQuoteRow.order_no.is_not(None),
        )
    ).all()
    return {header_order_no(r[0]) for r in rows if r[0]}


def is_sample_cost_order(
    order: SoOrderRow | None,
    *,
    quote_linked: set[str],
    source_order_no: str,
) -> bool:
    header = header_order_no(order.order_no if order else source_order_no)
    if order is not None and is_sample_cost_source(order.order_source):
        return True
    return header in quote_linked


def planned_labor_cost_by_product(
    session: Session,
    *,
    plan_version: int | None = None,
) -> dict:
    ver = plan_version if plan_version is not None else current_plan_version(session)
    empty_ex = {"hours_man": 0.0, "cost_planned": 0.0, "order_nos": []}
    if ver <= 0:
        return {
            "plan_version": ver,
            "products": [],
            "totals": {"hours_man": 0.0, "cost_planned": 0.0},
            "sample_excluded": empty_ex,
            "note": MASS_COST_NOTE,
        }

    tasks = session.scalars(select(WoTaskRow).where(WoTaskRow.plan_version == ver)).all()
    wos = {
        w.wo_no: w
        for w in session.scalars(select(WoRow).where(WoRow.plan_version == ver)).all()
    }
    orders = {o.order_no: o for o in session.scalars(select(SoOrderRow)).all()}
    quote_linked = quote_sample_order_nos(session)

    by_product: dict[str, dict] = {}
    ex_h = Decimal("0")
    ex_c = Decimal("0")
    ex_orders: set[str] = set()

    for t in tasks:
        wo = wos.get(t.wo_no)
        if wo is None:
            continue
        header = header_order_no(wo.source_order_no)
        order = orders.get(header)
        h = decimal_hours(t.hours_man)
        rate = _rate_for_group(session, t.dept, t.group_code)
        cost = labor_cost(h, rate)
        if is_sample_cost_order(order, quote_linked=quote_linked, source_order_no=wo.source_order_no):
            ex_h += h
            ex_c += cost
            ex_orders.add(header)
            continue
        product = order.item_code if order is not None else wo.item_code
        if product not in by_product:
            by_product[product] = {
                "item_code": product,
                "hours_man": Decimal("0"),
                "cost_planned": Decimal("0"),
                "order_nos": set(),
            }
        by_product[product]["hours_man"] += h
        by_product[product]["cost_planned"] += cost
        by_product[product]["order_nos"].add(header)

    products = []
    total_h = Decimal("0")
    total_c = Decimal("0")
    for p in sorted(by_product.values(), key=lambda x: x["item_code"]):
        total_h += p["hours_man"]
        total_c += p["cost_planned"]
        products.append(
            {
                "item_code": p["item_code"],
                "hours_man_planned": float(p["hours_man"]),
                "cost_planned": float(p["cost_planned"]),
                "order_count": len(p["order_nos"]),
                "order_nos": sorted(p["order_nos"]),
            }
        )

    return {
        "plan_version": ver,
        "products": products,
        "totals": {
            "hours_man": float(total_h),
            "cost_planned": float(total_c),
        },
        "sample_excluded": {
            "hours_man": float(ex_h),
            "cost_planned": float(ex_c),
            "order_nos": sorted(ex_orders),
        },
        "note": MASS_COST_NOTE,
    }


def product_labor_for_item(
    session: Session,
    item_code: str,
    *,
    plan_version: int | None = None,
    qty_order: float | None = None,
    unit: str | None = None,
) -> dict | None:
    data = planned_labor_cost_by_product(session, plan_version=plan_version)
    row = next((p for p in data["products"] if p["item_code"] == item_code), None)
    if row is None and data["plan_version"] <= 0:
        return None
    base = row or {
        "item_code": item_code,
        "hours_man_planned": 0.0,
        "cost_planned": 0.0,
        "order_count": 0,
        "order_nos": [],
    }
    out = {
        **base,
        "plan_version": data["plan_version"],
        "note": data.get("note"),
        "sample_excluded": data.get("sample_excluded"),
    }
    if qty_order and qty_order > 0 and row and row["order_count"] > 0:
        per_order_h = row["hours_man_planned"] / max(1, row["order_count"])
        per_order_c = row["cost_planned"] / max(1, row["order_count"])
        out["hint_per_order"] = {
            "hours_man_planned": round(per_order_h, 4),
            "cost_planned": round(per_order_c, 2),
        }
    if unit:
        out["unit"] = unit
    if qty_order is not None:
        out["qty_order"] = qty_order
    return out
