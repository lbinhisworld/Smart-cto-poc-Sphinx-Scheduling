"""一部产能统计 API。"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.prod_stats import dept1_daily, dept1_detail, dept1_efficiency
from db.prod_stats_seed import ensure_dept1_stats_seed
from db.tables import InvInboundDailyRow, MdItemRow
from shared.auth import user_for_role

READ_ROLES = frozenset({"GM", "PMC", "TEAM_LEADER", "FIN", "HR", "WH"})
WRITE_INBOUND = frozenset({"GM", "PMC", "WH"})


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def _require_read(role: str) -> None:
    if role not in READ_ROLES:
        raise HTTPException(status_code=403, detail="无权查看一部统计")


class InboundBody(BaseModel):
    work_date: date
    item_code: str
    qty_board: int = Field(..., ge=0)
    group_code: str = "MANUAL"
    note: str = ""


def register_prod_stats(app, get_db):
    @app.get("/api/prod-stats/dept1/detail")
    def api_dept1_detail(
        date_from: date,
        date_to: date,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _require_read(_role(x_demo_role))
        ensure_dept1_stats_seed(db)
        return {"code": 0, "message": "", "data": dept1_detail(db, date_from=date_from, date_to=date_to)}

    @app.get("/api/prod-stats/dept1/daily")
    def api_dept1_daily(
        date_from: date,
        date_to: date,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _require_read(_role(x_demo_role))
        ensure_dept1_stats_seed(db)
        return {"code": 0, "message": "", "data": dept1_daily(db, date_from=date_from, date_to=date_to)}

    @app.get("/api/prod-stats/dept1/efficiency")
    def api_dept1_efficiency(
        date_from: date,
        date_to: date,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _require_read(_role(x_demo_role))
        ensure_dept1_stats_seed(db)
        return {"code": 0, "message": "", "data": dept1_efficiency(db, date_from=date_from, date_to=date_to)}

    @app.post("/api/prod-stats/dept1/inbound")
    def api_dept1_inbound(
        body: InboundBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        if role not in WRITE_INBOUND:
            raise HTTPException(status_code=403, detail="无权登记入库")
        item = db.get(MdItemRow, body.item_code)
        if item is None:
            raise HTTPException(status_code=404, detail="品项不存在")
        user = user_for_role(role)
        row = InvInboundDailyRow(
            work_date=body.work_date,
            schedule_dept="FINISHED_DEPT",
            group_code=body.group_code,
            item_code=body.item_code,
            qty_board=body.qty_board,
            kg_per_board_snap=str(item.kg_per_board) if item.kg_per_board is not None else None,
            source="MOCK",
            note=body.note,
            created_at=datetime.now(),
            created_by=user.name if user else role,
        )
        db.add(row)
        db.flush()
        return {"code": 0, "message": "", "data": {"id": row.id}}
