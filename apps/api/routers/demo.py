"""Phase 8：演示控制台 + 待办中心。"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.services import flow as flow_service
from db.todo_center import list_todos
from shared.auth import user_for_role
from shared.demo_rehearsal import acts_for_api

SCOPE_SUMMARY = {
    "offline_ok": True,
    "disclaimer": "企微/日程为本地模拟，非真 SDK 推送",
    "not_delivered": [
        "入微云全量数据迁移",
        "费用政策与费用审批关联客户",
        "审批流可视化拖拽配置",
        "自定义报表设计器",
        "真企微 SDK、移动端离线",
    ],
    "crm_mapping_note": "销管清单 MUST：客户档案、漏斗、样品、字段权限、CTP、变更影响；SHOULD 可降级",
}


def _role(x_demo_role: str | None) -> str:
    if not x_demo_role or user_for_role(x_demo_role) is None:
        raise HTTPException(status_code=401, detail="缺少或无效 X-Demo-Role")
    return x_demo_role


def register_demo(app, get_db):
    @app.get("/api/demo/rehearsal")
    def rehearsal_script(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
        _role(x_demo_role)
        return {"code": 0, "message": "", "data": {"acts": acts_for_api(), "scope": SCOPE_SUMMARY}}

    @app.get("/api/demo/todos")
    def demo_todos(
        today: date | None = None,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        anchor = today or date(2026, 9, 15)
        items = list_todos(db, role=role, today=anchor)
        return {"code": 0, "message": "", "data": {"today": anchor.isoformat(), "items": items}}

    @app.post("/api/demo/trigger-sample-overdue")
    def trigger_sample_overdue(
        sample_code: str = Query(default="SP-001"),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        """联调用：触发 S5 超期打样模拟消息。"""
        role = _role(x_demo_role)
        if role not in ("GM", "SALES_MGR", "PMC"):
            raise HTTPException(status_code=403, detail="演示触发限 GM/销售总监/PMC")
        flow_service.on_sample_overdue(db, sample_code=sample_code)
        return {"code": 0, "message": "已写入企微模拟消息 S5", "data": {"sample_code": sample_code}}

    @app.get("/api/demo/scope")
    def demo_scope():
        return {"code": 0, "message": "", "data": SCOPE_SUMMARY}
