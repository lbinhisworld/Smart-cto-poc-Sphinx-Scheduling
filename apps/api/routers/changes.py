"""订单变更 + 影响清单。"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.services import flow as flow_service
from db.order_change_service import (
    approve_change_request,
    create_change_request,
    list_change_requests,
    reject_change_request,
)
from shared.auth import user_for_role


class ChangeSubmitBody(BaseModel):
    order_no: str
    new_due: date


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def register_changes(app, get_db):
    @app.get("/api/order-changes")
    def list_changes(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {"code": 0, "message": "", "data": list_change_requests(db)}

    @app.post("/api/order-changes")
    def submit_change(
        body: ChangeSubmitBody,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in ("SALES", "SALES_MGR", "GM"):
            raise HTTPException(status_code=403, detail="销售侧提交变更")
        user = user_for_role(role)
        anchor = today or date(2026, 9, 15)
        try:
            row = create_change_request(
                db,
                order_no=body.order_no,
                new_due=body.new_due,
                requested_by=user.name if user else role,
                requested_role=role,
                today=anchor,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="订单不存在") from exc
        flow_service.on_order_change_submitted(db, order_no=body.order_no, request_id=row.id)
        return {"code": 0, "message": "", "data": {"id": row.id, "status": row.status}}

    @app.post("/api/order-changes/{request_id}/approve")
    def approve_change(
        request_id: int,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        try:
            row = approve_change_request(db, request_id=request_id, approver_role=role)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="申请不存在") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        new_due = __import__("json").loads(row.new_value_json).get("due_date", "")
        flow_service.on_order_change_approved(db, order_no=row.order_no, new_due=new_due)
        return {"code": 0, "message": "", "data": {"id": row.id, "status": row.status}}

    @app.post("/api/order-changes/{request_id}/reject")
    def reject_change(
        request_id: int,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        try:
            row = reject_change_request(db, request_id=request_id, approver_role=role)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="申请不存在") from exc
        return {"code": 0, "message": "", "data": {"id": row.id, "status": row.status}}
