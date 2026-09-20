"""一单一议产品报价（MIS）。不进 engine，不写 so_order.due_date。"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.order_create_mis import create_mis_order
from db.tables import CrmCustomerRow, CrmQuoteLineRow, CrmQuoteRow, MdItemRow
from engine.models import Uom

PROCESS_LABEL = {
    "MANUAL": "手工",
    "MOLD": "模具",
    "POURING": "浇注",
    "SEMI": "半成品",
}

EDITABLE = frozenset({"DRAFT"})
VOIDABLE = frozenset({"DRAFT", "SUBMITTED", "APPROVED"})


def _json_ready(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_ready(v) for v in obj]
    return obj


def _d(val, default: str = "0") -> Decimal:
    if val is None or val == "":
        return Decimal(default)
    return Decimal(str(val))


def _optional_qty(val) -> Decimal | None:
    if val is None or val == "":
        return None
    return Decimal(str(val))


def process_label_for_item(item: MdItemRow | None) -> str:
    if item is None:
        return ""
    return PROCESS_LABEL.get(item.group_code, item.group_code or "")


def line_amounts(*, qty: Decimal, unit_price: Decimal, mold_fee: Decimal) -> tuple[Decimal, Decimal]:
    goods = (qty * unit_price).quantize(Decimal("0.01"))
    total = (goods + mold_fee).quantize(Decimal("0.01"))
    return goods, total


def _next_quote_code(session: Session) -> str:
    nums: list[int] = []
    for code in session.scalars(select(CrmQuoteRow.code)):
        if code.startswith("QT-") and code[3:].isdigit():
            nums.append(int(code[3:]))
    n = max(nums) + 1 if nums else 1
    return f"QT-{n:03d}"


def _normalize_raw_line(raw: dict, line_no: int) -> dict:
    if "item" in raw and "item_name" not in raw and "item_code" not in raw:
        return {
            "line_no": line_no,
            "item_code": None,
            "item_name": str(raw.get("item") or ""),
            "image_ref": "",
            "spec": "",
            "process_label": "",
            "category": "",
            "unit_price_tax_in": _d(raw.get("price")),
            "moq": None,
            "qty": _d(raw.get("qty"), "1"),
            "uom": str(raw.get("uom") or "BOX"),
            "mold_fee": _d(raw.get("mold_fee")),
            "rebate_qty": None,
            "rebate_uom": None,
            "note": str(raw.get("note") or ""),
        }
    moq = _optional_qty(raw.get("moq"))
    rebate = _optional_qty(raw.get("rebate_qty"))
    code = raw.get("item_code")
    code = str(code).strip() if code else None
    if code == "":
        code = None
    return {
        "line_no": line_no,
        "item_code": code,
        "item_name": str(raw.get("item_name") or ""),
        "image_ref": str(raw.get("image_ref") or ""),
        "spec": str(raw.get("spec") or ""),
        "process_label": str(raw.get("process_label") or ""),
        "category": str(raw.get("category") or ""),
        "unit_price_tax_in": _d(raw.get("unit_price_tax_in") or raw.get("price")),
        "moq": moq,
        "qty": _d(raw.get("qty"), "1"),
        "uom": str(raw.get("uom") or "BOX"),
        "mold_fee": _d(raw.get("mold_fee")),
        "rebate_qty": rebate,
        "rebate_uom": (str(raw["rebate_uom"]) if raw.get("rebate_uom") else None),
        "note": str(raw.get("note") or ""),
    }


def _validate_line(session: Session, parsed: dict, *, require_item: bool) -> None:
    qty = parsed["qty"]
    if qty <= 0 or qty != qty.to_integral_value():
        raise ValueError("需求量必须为正整数")
    parsed["qty"] = qty.to_integral_value()
    moq = parsed["moq"]
    if moq is not None:
        if moq <= 0 or moq != moq.to_integral_value():
            raise ValueError("起订量必须为正整数")
        parsed["moq"] = moq.to_integral_value()
        if parsed["qty"] < parsed["moq"]:
            raise ValueError("需求量低于起订量")
    if parsed["unit_price_tax_in"] < 0:
        raise ValueError("含税单价不能为负")
    if parsed["mold_fee"] < 0:
        raise ValueError("模具费用不能为负")
    try:
        Uom(parsed["uom"])
    except ValueError:
        raise ValueError(f"无效单位: {parsed['uom']}") from None
    code = parsed["item_code"]
    if require_item and not code:
        raise ValueError("转订单必须有已入库成品品项")
    if code:
        item = session.get(MdItemRow, code)
        if item is None:
            raise ValueError(f"品项不存在: {code}")
        if item.is_semi:
            raise ValueError(f"半成品不可作为报价/销售行: {code}")
        if not parsed["item_name"]:
            parsed["item_name"] = item.item_name
        if not parsed["process_label"]:
            parsed["process_label"] = process_label_for_item(item)
        if not parsed["category"]:
            parsed["category"] = getattr(item, "prod_category", "") or ""


def replace_quote_lines(session: Session, quote_code: str, lines: list[dict], *, require_item: bool = False) -> Decimal:
    if not lines:
        raise ValueError("至少一行报价明细")
    parsed_rows: list[dict] = []
    total = Decimal("0")
    for i, raw in enumerate(lines, start=1):
        parsed = _normalize_raw_line(raw, i)
        _validate_line(session, parsed, require_item=require_item)
        _goods, line_total = line_amounts(
            qty=parsed["qty"],
            unit_price=parsed["unit_price_tax_in"],
            mold_fee=parsed["mold_fee"],
        )
        parsed["line_goods_amount"] = _goods
        parsed["line_total"] = line_total
        total += line_total
        parsed_rows.append(parsed)

    session.execute(delete(CrmQuoteLineRow).where(CrmQuoteLineRow.quote_code == quote_code))
    for parsed in parsed_rows:
        session.add(
            CrmQuoteLineRow(
                quote_code=quote_code,
                line_no=parsed["line_no"],
                item_code=parsed["item_code"],
                item_name=parsed["item_name"],
                image_ref=parsed["image_ref"],
                spec=parsed["spec"],
                process_label=parsed["process_label"],
                category=parsed["category"],
                unit_price_tax_in=str(parsed["unit_price_tax_in"]),
                moq=str(parsed["moq"]) if parsed["moq"] is not None else None,
                qty=str(parsed["qty"]),
                uom=parsed["uom"],
                mold_fee=str(parsed["mold_fee"]),
                rebate_qty=str(parsed["rebate_qty"]) if parsed["rebate_qty"] is not None else None,
                rebate_uom=parsed["rebate_uom"],
                note=parsed["note"],
            )
        )
    return total.quantize(Decimal("0.01"))


def _serialize_line(row: CrmQuoteLineRow) -> dict:
    qty = _d(row.qty)
    price = _d(row.unit_price_tax_in)
    mold = _d(row.mold_fee)
    goods, total = line_amounts(qty=qty, unit_price=price, mold_fee=mold)
    return {
        "line_no": row.line_no,
        "item_code": row.item_code,
        "item_name": row.item_name,
        "image_ref": row.image_ref or "",
        "spec": row.spec or "",
        "process_label": row.process_label or "",
        "category": row.category or "",
        "unit_price_tax_in": float(price),
        "moq": float(row.moq) if row.moq is not None else None,
        "qty": float(qty),
        "uom": row.uom,
        "mold_fee": float(mold),
        "rebate_qty": float(row.rebate_qty) if row.rebate_qty is not None else None,
        "rebate_uom": row.rebate_uom,
        "note": row.note or "",
        "line_goods_amount": float(goods),
        "line_mold_amount": float(mold),
        "line_total": float(total),
    }


def _lines_for_quote(session: Session, quote: CrmQuoteRow) -> list[dict]:
    rows = session.scalars(
        select(CrmQuoteLineRow)
        .where(CrmQuoteLineRow.quote_code == quote.code)
        .order_by(CrmQuoteLineRow.line_no)
    ).all()
    if rows:
        return [_serialize_line(r) for r in rows]
    legacy = json.loads(quote.lines_json or "[]")
    out = []
    for i, raw in enumerate(legacy, start=1):
        parsed = _normalize_raw_line(raw, i)
        goods, total = line_amounts(
            qty=parsed["qty"],
            unit_price=parsed["unit_price_tax_in"],
            mold_fee=parsed["mold_fee"],
        )
        out.append(
            {
                **{
                    k: (
                        float(v)
                        if isinstance(v, Decimal)
                        else v
                    )
                    for k, v in parsed.items()
                },
                "line_goods_amount": float(goods),
                "line_mold_amount": float(parsed["mold_fee"]),
                "line_total": float(total),
                "moq": float(parsed["moq"]) if parsed["moq"] is not None else None,
                "rebate_qty": float(parsed["rebate_qty"]) if parsed["rebate_qty"] is not None else None,
            }
        )
    return out


def serialize_quote(session: Session, quote: CrmQuoteRow) -> dict:
    return {
        "code": quote.code,
        "customer_code": quote.customer_code,
        "sample_code": quote.sample_code,
        "total_amount": float(quote.total_amount),
        "status": quote.status,
        "owner_sales": quote.owner_sales,
        "opportunity_id": quote.opportunity_id,
        "tax_rate": float(quote.tax_rate) if quote.tax_rate is not None else 0.13,
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "contract_no": quote.contract_no,
        "order_no": quote.order_no,
        "note": quote.note or "",
        "lines": _lines_for_quote(session, quote),
    }


def list_quotes(
    session: Session,
    *,
    customer_code: str | None = None,
    status: str | None = None,
    hide_amount: bool = False,
) -> list[dict]:
    stmt = select(CrmQuoteRow).order_by(CrmQuoteRow.code)
    if customer_code:
        stmt = stmt.where(CrmQuoteRow.customer_code == customer_code)
    if status:
        stmt = stmt.where(CrmQuoteRow.status == status)
    out = [serialize_quote(session, q) for q in session.scalars(stmt)]
    if hide_amount:
        for row in out:
            row["total_amount"] = None
            for ln in row["lines"]:
                ln["unit_price_tax_in"] = None
                ln["mold_fee"] = None
                ln["line_goods_amount"] = None
                ln["line_mold_amount"] = None
                ln["line_total"] = None
    return out


def get_quote(session: Session, code: str) -> dict:
    row = session.get(CrmQuoteRow, code)
    if row is None:
        raise KeyError("报价单不存在")
    return serialize_quote(session, row)


def seed_quote_from_demo(session: Session, row: dict) -> None:
    """演示种子写入头 + 行。"""
    lines = row.get("lines") or []
    code = row["code"]
    session.add(
        CrmQuoteRow(
            code=code,
            customer_code=row["customer_code"],
            sample_code=row.get("sample_code"),
            total_amount=str(row.get("total_amount") or 0),
            status=row.get("status", "DRAFT"),
            owner_sales=row.get("owner_sales", ""),
            lines_json=json.dumps(lines, ensure_ascii=False),
            opportunity_id=row.get("opportunity_id"),
            tax_rate=str(row.get("tax_rate") or "0.13"),
            valid_until=date.fromisoformat(row["valid_until"]) if row.get("valid_until") else None,
            contract_no=row.get("contract_no"),
            order_no=row.get("order_no"),
            note=row.get("note") or "",
        )
    )
    session.flush()
    if lines:
        total = replace_quote_lines(session, code, lines, require_item=False)
        q = session.get(CrmQuoteRow, code)
        if q is not None:
            q.total_amount = str(total)


def create_quote(
    session: Session,
    *,
    customer_code: str,
    lines: list[dict],
    sample_code: str | None = None,
    owner_sales: str = "",
    opportunity_id: int | None = None,
    tax_rate: Decimal | None = None,
    valid_until: date | None = None,
    note: str = "",
) -> dict:
    customer = session.get(CrmCustomerRow, customer_code)
    if customer is None:
        raise ValueError("客户不存在")
    code = _next_quote_code(session)
    session.add(
        CrmQuoteRow(
            code=code,
            customer_code=customer_code,
            sample_code=sample_code,
            total_amount="0",
            status="DRAFT",
            owner_sales=owner_sales or customer.owner_sales,
            lines_json="[]",
            opportunity_id=opportunity_id,
            tax_rate=str(tax_rate if tax_rate is not None else Decimal("0.13")),
            valid_until=valid_until,
            note=note,
        )
    )
    session.flush()
    total = replace_quote_lines(session, code, lines, require_item=False)
    q = session.get(CrmQuoteRow, code)
    assert q is not None
    q.total_amount = str(total)
    q.lines_json = json.dumps(_json_ready(lines), ensure_ascii=False)
    session.flush()
    return serialize_quote(session, q)


def update_quote(
    session: Session,
    code: str,
    *,
    lines: list[dict] | None = None,
    sample_code: str | None = None,
    owner_sales: str | None = None,
    opportunity_id: int | None = None,
    tax_rate: Decimal | None = None,
    valid_until: date | None = None,
    note: str | None = None,
    customer_code: str | None = None,
) -> dict:
    q = session.get(CrmQuoteRow, code)
    if q is None:
        raise KeyError("报价单不存在")
    if q.status not in EDITABLE:
        raise ValueError("仅草稿可修改")
    if customer_code is not None:
        if session.get(CrmCustomerRow, customer_code) is None:
            raise ValueError("客户不存在")
        q.customer_code = customer_code
    if sample_code is not None:
        q.sample_code = sample_code
    if owner_sales is not None:
        q.owner_sales = owner_sales
    if opportunity_id is not None:
        q.opportunity_id = opportunity_id
    if tax_rate is not None:
        q.tax_rate = str(tax_rate)
    if valid_until is not None:
        q.valid_until = valid_until
    if note is not None:
        q.note = note
    if lines is not None:
        total = replace_quote_lines(session, code, lines, require_item=False)
        q.total_amount = str(total)
        q.lines_json = json.dumps(_json_ready(lines), ensure_ascii=False)
    session.flush()
    return serialize_quote(session, q)


def submit_quote(session: Session, code: str) -> dict:
    q = session.get(CrmQuoteRow, code)
    if q is None:
        raise KeyError("报价单不存在")
    if q.status != "DRAFT":
        raise ValueError("仅草稿可提交")
    q.status = "SUBMITTED"
    session.flush()
    return serialize_quote(session, q)


def approve_quote(session: Session, code: str) -> dict:
    q = session.get(CrmQuoteRow, code)
    if q is None:
        raise KeyError("报价单不存在")
    if q.status != "SUBMITTED":
        raise ValueError("仅已提交报价可批准")
    q.status = "APPROVED"
    session.flush()
    return serialize_quote(session, q)


def void_quote(session: Session, code: str) -> dict:
    q = session.get(CrmQuoteRow, code)
    if q is None:
        raise KeyError("报价单不存在")
    if q.status not in VOIDABLE:
        raise ValueError("已转订单不可作废")
    q.status = "VOID"
    session.flush()
    return serialize_quote(session, q)


def convert_to_order(
    session: Session,
    *,
    quote_code: str,
    contract_no: str,
    due_date: date,
    today: date,
    sales_name: str = "",
    is_urgent: bool = False,
) -> dict:
    q = session.get(CrmQuoteRow, quote_code)
    if q is None:
        raise KeyError("报价单不存在")
    if q.status != "APPROVED":
        raise ValueError("仅已批准报价可转订单")
    if q.order_no:
        raise ValueError("该报价已转订单")
    lines = _lines_for_quote(session, q)
    if not lines:
        raise ValueError("报价无明细")
    order_lines: list[dict] = []
    for ln in lines:
        if not ln.get("item_code"):
            raise ValueError("转订单必须有已入库成品品项")
        price = _d(ln.get("unit_price_tax_in"))
        if price <= 0:
            raise ValueError("报价转单必须填写含税单价")
        order_lines.append(
            {
                "item_code": ln["item_code"],
                "qty": ln["qty"],
                "unit": ln.get("uom") or "BOX",
                "unit_price": price,
                "spec": ln.get("spec") or "",
                "mold_fee": _d(ln.get("mold_fee")),
                "rebate_qty": ln.get("rebate_qty"),
                "note": ln.get("note") or "",
            }
        )
    created = create_mis_order(
        session,
        customer_code=q.customer_code,
        contract_no=contract_no,
        lines=order_lines,
        due_date=due_date,
        today=today,
        sales_name=sales_name or q.owner_sales,
        is_urgent=is_urgent,
        quote_no=quote_code,
        allow_default_price=False,
    )
    q.status = "CONVERTED"
    q.order_no = created["order_no"]
    q.contract_no = contract_no
    session.flush()
    created["quote_code"] = quote_code
    created["quote"] = serialize_quote(session, q)
    return created
