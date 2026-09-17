"""M3 金蝶 Push 模拟工作台。"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.demo_crm_seed import ensure_demo_crm
from db.master_data_kingdee import sync_raw_materials_from_mock, sync_suppliers_from_mock
from db.tables import KingdeeSyncLogRow
from integrations.kingdee_adapter import MockKingdeeAdapter, PushOrderPayload
from shared.auth import user_for_role

ROOT = Path(__file__).resolve().parents[3]
DEMO_PATH = ROOT / "seed" / "demo_data.json"


class SimulatePushBody(BaseModel):
    template_key: str | None = Field(default=None, description="demo_data.kingdee_templates 键")
    order_no: str | None = None


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    if x_demo_role not in ("GM", "PMC", "WH"):
        raise HTTPException(status_code=403, detail="仅 GM/PMC/仓库可操作金蝶模拟")
    return x_demo_role


def _templates() -> dict:
    if not DEMO_PATH.is_file():
        return {}
    data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    return data.get("kingdee_templates") or {}


def register_kingdee(app, get_db):
    @app.get("/api/kingdee/logs")
    def list_logs(
        limit: int = 50,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        rows = db.scalars(
            select(KingdeeSyncLogRow).order_by(KingdeeSyncLogRow.id.desc()).limit(min(limit, 200))
        ).all()
        return {
            "code": 0,
            "message": "",
            "data": [
                {
                    "id": r.id,
                    "direction": r.direction,
                    "doc_type": r.doc_type,
                    "doc_no": r.doc_no,
                    "status": r.status,
                    "message": r.message,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }

    @app.get("/api/kingdee/templates")
    def list_templates(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
        _role(x_demo_role)
        tpl = _templates()
        return {
            "code": 0,
            "message": "",
            "data": [{"key": k, **v} for k, v in tpl.items()],
        }

    @app.post("/api/kingdee/simulate-push")
    def simulate_push(
        body: SimulatePushBody,
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ensure_demo_crm(db)
        anchor = today or date(2026, 9, 15)
        tpl_all = _templates()
        key = body.template_key or next(iter(tpl_all.keys()), None)
        if not key or key not in tpl_all:
            raise HTTPException(status_code=400, detail="无可用推送模板")
        tpl = tpl_all[key]
        import time

        suffix = int(time.time() * 1000) % 100000
        order_no = body.order_no or tpl.get("order_no") or f"SO-KD-{key}-{suffix}"

        payload = PushOrderPayload(
            order_no=order_no,
            customer=tpl["customer"],
            sales_name=tpl.get("sales_name", ""),
            item_code=tpl["item_code"],
            qty_order=Decimal(str(tpl["qty_order"])),
            unit=tpl["unit"],
            due_date=date.fromisoformat(tpl["due_date"]),
            amount=Decimal(str(tpl.get("amount", 0))),
            customer_code=tpl.get("customer_code"),
        )
        adapter = MockKingdeeAdapter()
        log = adapter.push_order(db, payload, today=anchor)
        db.flush()
        return {
            "code": 0 if log.status == "SUCCESS" else 409,
            "message": log.message,
            "data": {
                "log_id": log.id,
                "order_no": log.doc_no,
                "status": log.status,
            },
        }

    @app.post("/api/kingdee/sync-suppliers")
    def sync_suppliers(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        log = sync_suppliers_from_mock(db)
        db.flush()
        return {
            "code": 0 if log.status == "SUCCESS" else 409,
            "message": log.message,
            "data": {"log_id": log.id, "status": log.status},
        }

    @app.post("/api/kingdee/sync-raw-materials")
    def sync_raw_materials(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        log = sync_raw_materials_from_mock(db)
        db.flush()
        return {
            "code": 0 if log.status == "SUCCESS" else 409,
            "message": log.message,
            "data": {"log_id": log.id, "status": log.status},
        }
