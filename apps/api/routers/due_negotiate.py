"""协商交期：口径预览/发送、销售回日、PMC 改锚、时间线。"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.services import flow as flow_service
from db.due_negotiate import (
    apply_negotiated_due,
    get_negotiate,
    list_due_events,
    list_open_negotiations,
    preview_brief,
    sales_reply_due,
    send_sales_brief,
)
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


class BriefBody(BaseModel):
    order_no: str
    suggested_due: date
    conflict_code: str = "E2"
    reason: str = "半成品来不及"
    run_id: str = ""
    brief_text: str | None = None


class ReplyBody(BaseModel):
    proposed_due: date
    request_id: int
    note: str = ""


class ApplyBody(BaseModel):
    request_id: int
    today: date | None = None


def register_due_negotiate(app, get_db):
    @app.post("/api/schedule/assist/brief/preview")
    def assist_brief_preview(
        body: BriefBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        try:
            data = preview_brief(
                db,
                order_no=body.order_no,
                suggested_due=body.suggested_due,
                conflict_code=body.conflict_code,
                reason=body.reason,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="订单不存在") from None
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/schedule/assist/brief")
    def assist_brief_send(
        body: BriefBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        user = user_for_role(role)
        try:
            row = send_sales_brief(
                db,
                order_no=body.order_no,
                suggested_due=body.suggested_due,
                conflict_code=body.conflict_code,
                reason=body.reason,
                actor=user.name if user else role,
                role=role,
                run_id=body.run_id,
                brief_text=body.brief_text,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="订单不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from None
        old_due = __import__("json").loads(row.old_value_json).get("due_date", "")
        flow_service.on_due_negotiate_ask(
            db,
            order_no=row.order_no,
            request_id=row.id,
            old_due=old_due,
            suggested_due=body.suggested_due.isoformat(),
            brief_text=row.brief_text,
        )
        return {"code": 0, "message": "", "data": {"id": row.id, "status": row.status}}

    @app.get("/api/due-negotiations")
    def due_negotiations(
        order_no: str | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {"code": 0, "message": "", "data": {"items": list_open_negotiations(db, order_no=order_no)}}

    @app.post("/api/orders/{order_no}/due-negotiate/reply")
    def due_negotiate_reply(
        order_no: str,
        body: ReplyBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        user = user_for_role(role)
        try:
            row = sales_reply_due(
                db,
                request_id=body.request_id,
                proposed_due=body.proposed_due,
                actor=user.name if user else role,
                role=role,
                note=body.note,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="申请不存在") from None
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        if row.order_no != order_no:
            raise HTTPException(status_code=409, detail="订单号与申请不一致")
        flow_service.on_due_negotiate_reply(
            db,
            order_no=row.order_no,
            request_id=row.id,
            proposed_due=body.proposed_due.isoformat(),
        )
        return {"code": 0, "message": "", "data": {"id": row.id, "status": row.status}}

    @app.post("/api/orders/{order_no}/due-negotiate/apply")
    def due_negotiate_apply(
        order_no: str,
        body: ApplyBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        try:
            row = apply_negotiated_due(
                db,
                request_id=body.request_id,
                role=role,
                today=body.today or date(2026, 9, 15),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except KeyError:
            raise HTTPException(status_code=404, detail="申请不存在") from None
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        if row.order_no != order_no:
            raise HTTPException(status_code=409, detail="订单号与申请不一致")
        old_due = __import__("json").loads(row.old_value_json).get("due_date", "")
        new_due = row.sales_proposed_due.isoformat() if row.sales_proposed_due else ""
        flow_service.on_due_negotiate_applied(
            db,
            order_no=row.order_no,
            request_id=row.id,
            old_due=old_due,
            new_due=new_due,
        )
        return {
            "code": 0,
            "message": "交期已改锚，请再倒排",
            "data": {"id": row.id, "status": row.status, "impact": get_negotiate(db, row.id)},
        }

    @app.get("/api/orders/{order_no}/due-events")
    def due_events(
        order_no: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {
            "code": 0,
            "message": "",
            "data": {
                "events": list_due_events(db, order_no),
                "open": list_open_negotiations(db, order_no=order_no),
            },
        }
