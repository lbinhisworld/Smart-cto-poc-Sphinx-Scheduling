"""MIS 新建销售订单（头表 + 多行明细）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.contract_queries import validate_order_contract
from db.order_kitting import refresh_order_kitting
from db.repositories import list_order_nos
from db.tables import CrmCustomerRow, MdItemRow, SoOrderLineRow, SoOrderRow
from engine.models import Uom


def _next_order_no(session: Session) -> str:
    nums: list[int] = []
    for no in list_order_nos(session):
        if no.startswith("SO-") and no[3:].isdigit():
            nums.append(int(no[3:]))
    n = max(nums) + 1 if nums else 910
    if n < 910:
        n = 910
    return f"SO-{n:03d}"


def create_mis_order(
    session: Session,
    *,
    customer_code: str,
    contract_no: str,
    lines: list[dict],
    due_date: date,
    today: date,
    sales_name: str = "",
    is_urgent: bool = False,
    quote_no: str | None = None,
    allow_default_price: bool = True,
) -> dict:
    if not lines:
        raise ValueError("至少选择一行产品")
    customer = session.get(CrmCustomerRow, customer_code)
    if customer is None:
        raise ValueError("客户不存在")
    validate_order_contract(session, customer_code=customer_code, contract_no=contract_no)

    parsed: list[dict] = []
    total = Decimal("0")
    for i, ln in enumerate(lines, start=1):
        code = ln["item_code"]
        item = session.get(MdItemRow, code)
        if item is None:
            raise ValueError(f"品项不存在: {code}")
        if item.is_semi:
            raise ValueError(f"半成品不可作为销售行: {code}")
        qty = Decimal(str(ln["qty"]))
        if qty <= 0 or qty != qty.to_integral_value():
            raise ValueError("数量必须为正整数")
        qty = qty.to_integral_value()
        unit = ln.get("unit") or item.unit_sale or "BOX"
        try:
            Uom(unit)
        except ValueError:
            raise ValueError(f"无效单位: {unit}") from None
        unit_price = Decimal(str(ln.get("unit_price") or 0))
        if unit_price <= 0:
            if not allow_default_price:
                raise ValueError("报价转单必须填写含税单价")
            unit_price = Decimal("100")
        mold_fee = Decimal(str(ln.get("mold_fee") or 0))
        if mold_fee < 0:
            raise ValueError("模具费用不能为负")
        rebate_qty = ln.get("rebate_qty")
        rebate_dec = Decimal(str(rebate_qty)) if rebate_qty not in (None, "") else None
        line_amount = (qty * unit_price + mold_fee).quantize(Decimal("0.01"))
        total += line_amount
        parsed.append(
            {
                "line_no": i,
                "item_code": code,
                "item_name": item.item_name,
                "qty": qty,
                "unit": unit,
                "unit_price": unit_price,
                "line_amount": line_amount,
                "spec": str(ln.get("spec") or ""),
                "mold_fee": mold_fee,
                "rebate_qty": rebate_dec,
                "note": str(ln.get("note") or ""),
            }
        )

    first = parsed[0]
    order_no = _next_order_no(session)
    owner = sales_name or customer.owner_sales
    session.add(
        SoOrderRow(
            order_no=order_no,
            customer=customer.name,
            sales_name=owner,
            customer_code=customer_code,
            owner_sales=customer.owner_sales,
            item_code=first["item_code"],
            qty_order=str(first["qty"]),
            unit=first["unit"],
            due_date=due_date,
            ready_date=today,
            customer_level=customer.level,
            amount=str(total),
            is_urgent=is_urgent,
            schedule_phase="PENDING",
            order_status="CONFIRMED",
            order_source="MIS",
            kitting_rate_pct=None,
            contract_no=contract_no,
            quote_no=quote_no,
        )
    )
    for ln in parsed:
        session.add(
            SoOrderLineRow(
                order_no=order_no,
                line_no=ln["line_no"],
                item_code=ln["item_code"],
                item_name=ln["item_name"],
                qty=str(ln["qty"]),
                unit=ln["unit"],
                unit_price=str(ln["unit_price"]),
                line_amount=str(ln["line_amount"]),
                spec=ln["spec"],
                mold_fee=str(ln["mold_fee"]),
                rebate_qty=str(ln["rebate_qty"]) if ln["rebate_qty"] is not None else None,
                note=ln["note"],
            )
        )
    session.flush()
    kit = refresh_order_kitting(session, order_no, today=today)
    row = session.get(SoOrderRow, order_no)
    if row and kit.get("kitting_rate_pct") is not None:
        row.kitting_rate_pct = int(kit["kitting_rate_pct"])
    return {
        "order_no": order_no,
        "customer_code": customer_code,
        "line_count": len(parsed),
        "amount": float(total),
        "schedule_phase": "PENDING",
        "order_status": "CONFIRMED",
        "quote_no": quote_no,
    }
