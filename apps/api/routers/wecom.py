"""M9 企微/日程模拟。"""

from __future__ import annotations

import json

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.tables import WecomMessageRow, WecomScheduleEventRow
from shared.auth import user_for_role


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def register_wecom(app, get_db):
    @app.get("/api/wecom/messages")
    def list_messages(
        limit: int = 30,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        rows = db.scalars(
            select(WecomMessageRow).order_by(WecomMessageRow.id.desc()).limit(min(limit, 100))
        ).all()
        out = []
        for r in rows:
            targets = json.loads(r.role_targets_json or "[]")
            if targets and role not in targets and role != "GM":
                continue
            out.append(
                {
                    "id": r.id,
                    "scene": r.scene,
                    "title": r.title,
                    "body": r.body,
                    "deep_link": r.deep_link,
                    "is_read": r.is_read,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
            )
        return {"code": 0, "message": "", "data": out}

    @app.post("/api/wecom/messages/{msg_id}/read")
    def mark_read(msg_id: int, db: Session = Depends(get_db), x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
        _role(x_demo_role)
        row = db.get(WecomMessageRow, msg_id)
        if row:
            row.is_read = True
        return {"code": 0, "message": "", "data": {"id": msg_id}}

    @app.get("/api/wecom/schedule-events")
    def list_events(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        rows = db.scalars(
            select(WecomScheduleEventRow).order_by(WecomScheduleEventRow.start_at.desc()).limit(50)
        ).all()
        return {
            "code": 0,
            "message": "",
            "data": [
                {
                    "id": r.id,
                    "scene": r.scene,
                    "title": r.title,
                    "start_at": r.start_at.isoformat() if r.start_at else None,
                    "end_at": r.end_at.isoformat() if r.end_at else None,
                    "deep_link": r.deep_link,
                }
                for r in rows
            ],
        }
