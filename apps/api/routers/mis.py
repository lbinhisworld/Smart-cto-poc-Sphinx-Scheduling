"""MIS 列表 API（订单等）。"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.demo_crm_seed import ensure_demo_crm
from db.mis_orders import list_mis_orders
from db.order_create_mis import create_mis_order
from db.order_lines import cancel_order, ensure_order_lines, lines_for_order
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


class MisOrderLineIn(BaseModel):
    item_code: str
    qty: int = Field(gt=0)
    unit: str = "BOX"
    unit_price: float = Field(default=0, ge=0)


class MisCreateOrderIn(BaseModel):
    customer_code: str
    contract_no: str
    due_date: date
    lines: list[MisOrderLineIn] = Field(min_length=1)
    sales_name: str = ""
    is_urgent: bool = False


def register_mis(app, get_db):
    @app.post("/api/mis/orders")
    def mis_create_order(
        body: MisCreateOrderIn,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "SALES", "SALES_MGR", "PMC"):
            raise HTTPException(status_code=403, detail="无权新建订单")
        ensure_demo_crm(db)
        anchor = today or date(2026, 9, 15)
        try:
            out = create_mis_order(
                db,
                customer_code=body.customer_code,
                contract_no=body.contract_no,
                lines=[ln.model_dump() for ln in body.lines],
                due_date=body.due_date,
                today=anchor,
                sales_name=body.sales_name,
                is_urgent=body.is_urgent,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {"code": 0, "message": "订单已创建", "data": out}

    @app.get("/api/mis/orders")
    def mis_orders(
        view: str = "all",
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_demo_crm(db)
        ensure_order_lines(db)
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
        from db.hr_seed import ensure_hr_seed

        stats = ensure_demo_crm(db)
        stats["order_lines"] = ensure_order_lines(db)
        stats["hr"] = ensure_hr_seed(db)
        return {"code": 0, "message": "", "data": stats}

    @app.get("/api/mis/orders/{order_no}")
    def mis_order_detail(
        order_no: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        ensure_order_lines(db)
        from db.tables import SoOrderRow

        row = db.get(SoOrderRow, order_no)
        if row is None or row.order_status == "CANCELLED":
            raise HTTPException(status_code=404, detail="订单不存在")
        lines = lines_for_order(db, order_no)
        can_change = role in ("GM", "SALES", "SALES_MGR", "PMC")
        can_delete = role in ("GM", "PMC", "SALES_MGR")
        return {
            "code": 0,
            "message": "",
            "data": {
                "order_no": row.order_no,
                "customer": row.customer,
                "customer_code": row.customer_code,
                "sales_name": row.sales_name,
                "due_date": row.due_date.isoformat(),
                "amount": float(row.amount),
                "order_status": row.order_status,
                "schedule_phase": row.schedule_phase,
                "kitting_rate_pct": row.kitting_rate_pct,
                "lines": lines,
                "actions": {"can_change": can_change, "can_delete": can_delete},
            },
        }

    @app.delete("/api/mis/orders/{order_no}")
    def mis_order_cancel(
        order_no: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("GM", "PMC", "SALES_MGR"):
            raise HTTPException(status_code=403, detail="无权作废订单")
        try:
            cancel_order(db, order_no)
        except KeyError:
            raise HTTPException(status_code=404, detail="订单不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return {"code": 0, "message": "订单已作废", "data": {"order_no": order_no}}

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
