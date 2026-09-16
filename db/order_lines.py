"""销售订单行（一订单多品项 · 演示）。"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.tables import MdItemRow, SoOrderLineRow, SoOrderRow

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "seed" / "demo_data.json"
LINES_VERSION_KEY = "order_lines_version"


def _load_lines_spec() -> dict:
    if not DEMO_PATH.is_file():
        return {}
    data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    return data.get("order_lines") or {}


def _item_name(session: Session, code: str) -> str:
    row = session.get(MdItemRow, code)
    return row.item_name if row else code


def lines_for_order(session: Session, order_no: str) -> list[dict]:
    rows = session.scalars(
        select(SoOrderLineRow)
        .where(SoOrderLineRow.order_no == order_no)
        .order_by(SoOrderLineRow.line_no)
    ).all()
    if rows:
        return [
            {
                "line_no": r.line_no,
                "item_code": r.item_code,
                "item_name": r.item_name or r.item_code,
                "qty": float(r.qty),
                "unit": r.unit,
                "unit_price": float(r.unit_price),
                "line_amount": float(r.line_amount),
            }
            for r in rows
        ]
    header = session.get(SoOrderRow, order_no)
    if header is None:
        return []
    qty = float(header.qty_order)
    amt = float(header.amount)
    price = round(amt / qty, 4) if qty else 0
    return [
        {
            "line_no": 1,
            "item_code": header.item_code,
            "item_name": _item_name(session, header.item_code),
            "qty": qty,
            "unit": header.unit,
            "unit_price": price,
            "line_amount": amt,
        }
    ]


def lines_summary(lines: list[dict]) -> str:
    parts: list[str] = []
    for ln in lines[:3]:
        parts.append(f"{ln['item_code']}×{ln['qty']:g}{ln['unit']}")
    if len(lines) > 3:
        parts.append(f"等{len(lines)}行")
    return " · ".join(parts)


def ensure_order_lines(session: Session) -> dict:
    """按 demo_data.order_lines 灌入；版本变更时重建行表。"""
    from db.tables import AppSettingRow

    spec = _load_lines_spec()
    meta = json.loads(DEMO_PATH.read_text(encoding="utf-8")).get("meta", {}) if DEMO_PATH.is_file() else {}
    version = str(meta.get("demo_version", "lines-v1"))
    stored = session.get(AppSettingRow, LINES_VERSION_KEY)
    if stored and stored.value == version:
        return {"synced": False, "lines": 0}

    session.execute(delete(SoOrderLineRow))
    count = 0
    for order_no, line_rows in spec.items():
        if session.get(SoOrderRow, order_no) is None:
            continue
        for row in line_rows:
            qty = Decimal(str(row["qty"]))
            unit_price = Decimal(str(row.get("unit_price", 0)))
            line_amount = Decimal(str(row.get("line_amount", float(qty * unit_price))))
            session.add(
                SoOrderLineRow(
                    order_no=order_no,
                    line_no=int(row["line_no"]),
                    item_code=row["item_code"],
                    item_name=row.get("item_name") or _item_name(session, row["item_code"]),
                    qty=str(qty),
                    unit=row["unit"],
                    unit_price=str(unit_price),
                    line_amount=str(line_amount),
                )
            )
            count += 1

    row = session.get(AppSettingRow, LINES_VERSION_KEY)
    if row is None:
        session.add(AppSettingRow(key=LINES_VERSION_KEY, value=version))
    else:
        row.value = version
    return {"synced": True, "lines": count}


def cancel_order(session: Session, order_no: str) -> None:
    row = session.get(SoOrderRow, order_no)
    if row is None:
        raise KeyError(order_no)
    if row.order_status == "CANCELLED":
        raise ValueError("订单已作废")
    if (row.schedule_phase or "") == "IN_SCHEDULING":
        raise ValueError("订单在排程池中，请先移出再作废")
    row.order_status = "CANCELLED"
