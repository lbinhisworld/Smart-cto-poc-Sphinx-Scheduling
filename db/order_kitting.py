"""订单级算料 / 齐套率（M4，不跑全量倒排）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from db.bom_view import bom_explode
from db.tables import SoOrderRow


def refresh_order_kitting(session: Session, order_no: str, *, today: date) -> dict:
    row = session.get(SoOrderRow, order_no)
    if row is None:
        raise KeyError(order_no)

    ex = bom_explode(
        session,
        row.item_code,
        Decimal(str(row.qty_order)),
        row.unit,
        today=today,
    )
    if ex is None:
        row.kitting_rate_pct = None
        return {"order_no": order_no, "kitting_rate_pct": None, "computable": False}

    if not ex.get("computable"):
        row.kitting_rate_pct = None
        return {
            "order_no": order_no,
            "kitting_rate_pct": None,
            "computable": False,
            "message": ex.get("message"),
        }

    lines = ex.get("line_details") or []
    shortages: list[dict] = []
    if lines:
        ok = 0
        for ln in lines:
            short = int(ln.get("shortage_board") or 0)
            if short <= 0:
                ok += 1
            else:
                shortages.append(
                    {
                        "item_code": ln.get("component_item_code"),
                        "shortage_board": short,
                        "role": ln.get("role"),
                    }
                )
        rate = int(round(100 * ok / len(lines)))
    else:
        semi = ex.get("semi")
        if semi and semi.get("net_board", 0) > 0 and semi.get("stock_available", 0) < semi.get("gross_board", 0):
            rate = 82
            shortages.append({"item_code": semi.get("semi_item_code"), "note": "半成品净需求占用"})
        else:
            rate = 100

    row.kitting_rate_pct = rate
    return {
        "order_no": order_no,
        "kitting_rate_pct": rate,
        "computable": True,
        "shortages": shortages,
        "line_count": len(lines),
        "explode_summary": {
            "finished_plan_board": ex.get("finished_plan_board"),
            "semi": ex.get("semi"),
        },
    }
