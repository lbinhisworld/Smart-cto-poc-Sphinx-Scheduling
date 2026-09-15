"""库存读写（本地演示库；未来由 ERP Provider 同步）。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.tables import MdItemRow, StockRow


def _dec(value) -> Decimal:
    return Decimal(str(value))


def list_stock_rows(session: Session) -> list[dict]:
    items = {r.item_code: r.item_name for r in session.scalars(select(MdItemRow)).all()}
    rows = session.scalars(select(StockRow).order_by(StockRow.item_code)).all()
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "item_code": r.item_code,
                "item_name": items.get(r.item_code, r.item_code),
                "qty_available": float(_dec(r.qty_available)),
                "uom_display": r.uom_display or "BOARD",
                "source": r.source or "SEED",
                "warehouse_code": r.warehouse_code,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
        )
    return out


def stock_snapshot(session: Session) -> dict[str, Decimal]:
    return {
        r.item_code: _dec(r.qty_available)
        for r in session.scalars(select(StockRow)).all()
    }


def update_stock_qty(
    session: Session,
    item_code: str,
    qty_available: Decimal,
    *,
    source: str = "LOCAL",
) -> dict | None:
    row = session.get(StockRow, item_code)
    if row is None:
        return None
    row.qty_available = str(qty_available)
    row.source = source
    row.updated_at = datetime.now(UTC)
    session.flush()
    name = session.scalar(
        select(MdItemRow.item_name).where(MdItemRow.item_code == item_code)
    )
    return {
        "item_code": item_code,
        "item_name": name or item_code,
        "qty_available": float(qty_available),
        "uom_display": row.uom_display or "BOARD",
        "source": row.source,
        "warehouse_code": row.warehouse_code,
        "updated_at": row.updated_at.isoformat(),
    }


def bulk_upsert_stock(
    session: Session,
    entries: list[dict],
    *,
    source: str,
    mode: str = "merge",
) -> int:
    """mode=replace 清空后写入；merge 按 item_code upsert。"""
    if mode == "replace":
        session.execute(delete(StockRow))
    count = 0
    now = datetime.now(UTC)
    for e in entries:
        code = e["item_code"]
        qty = _dec(e["qty"])
        row = session.get(StockRow, code)
        if row is None:
            row = StockRow(
                item_code=code,
                qty_available=str(qty),
                uom_display=e.get("uom", "BOARD"),
                source=source,
                warehouse_code=e.get("warehouse_code"),
                updated_at=now,
            )
            session.add(row)
        else:
            row.qty_available = str(qty)
            row.uom_display = e.get("uom", row.uom_display or "BOARD")
            row.source = source
            row.warehouse_code = e.get("warehouse_code", row.warehouse_code)
            row.updated_at = now
        count += 1
    session.flush()
    return count
