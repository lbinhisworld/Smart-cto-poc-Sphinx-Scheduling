"""MIS 列表 API（订单等）。"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db.demo_crm_seed import ensure_demo_crm
from db.mis_orders import list_mis_orders
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def register_mis(app, get_db):
    @app.get("/api/mis/orders")
    def mis_orders(
        view: str = "all",
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        db.flush()
        anchor = today or date(2026, 9, 15)
        rows, stats = list_mis_orders(db, role=role, view=view, today=anchor)
        hide_amount = role == "SALES"
        if hide_amount:
            for r in rows:
                r["amount"] = None
        return {
            "code": 0,
            "message": "",
            "data": {
                "view": view,
                "today": anchor.isoformat(),
                "role": role,
                "stats": stats,
                "rows": rows,
                "field_perm": {"amount_hidden": hide_amount},
            },
        }

    @app.post("/api/demo/ensure-crm-seed")
    def ensure_crm(db: Session = Depends(get_db)):
        stats = ensure_demo_crm(db)
        return {"code": 0, "message": "", "data": stats}

    @app.get("/api/mis/orders/{order_no}/breakdown")
    def mis_order_breakdown(
        order_no: str,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        from db.order_breakdown import order_breakdown

        anchor = today or date(2026, 9, 15)
        data = order_breakdown(db, order_no, today=anchor)
        if data is None:
            raise HTTPException(status_code=404, detail="订单不存在")
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/mis/orders/scheduling-pool")
    def mis_add_pool(
        body: dict,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC"):
            raise HTTPException(status_code=403, detail="仅 PMC/总经理可加入排产池")
        from db.order_lifecycle import add_to_scheduling_pool, scheduling_pool_order_nos

        order_nos = body.get("order_nos") or []
        if not order_nos:
            raise HTTPException(status_code=400, detail="order_nos 不能为空")
        try:
            add_to_scheduling_pool(db, order_nos)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "code": 0,
            "message": "",
            "data": {"pool": scheduling_pool_order_nos(db), "added": order_nos},
        }
