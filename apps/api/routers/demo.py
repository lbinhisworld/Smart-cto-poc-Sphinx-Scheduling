"""Phase 8：演示控制台 + 待办中心 + 场景台。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.services import flow as flow_service
from db.demo_scenario import (
    apply_roster,
    audit_scenario,
    generate_orders,
    reset_order_scenario,
    restore_official_seed,
    scenario_status,
)
from db.todo_center import list_todos
from shared.auth import user_for_role
from shared.demo_rehearsal import acts_for_api
from shared.demo_scenario import (
    DueMode,
    ItemShareMode,
    ScenarioPlanError,
    loop_acts_for_api,
    plan_orders,
    plan_to_api,
)

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


def _require_gm(role: str) -> None:
    if role != "GM":
        raise HTTPException(status_code=403, detail="场景台写操作仅总经理")


class GenerateOrdersBody(BaseModel):
    order_count: Literal[5, 10, 20, 50, 100]
    due_mode: Literal["FOCUS_FENCE", "FOCUS_MID", "FOCUS_FAR", "UNIFORM"]
    item_share: Literal["NONE", "SHARE_10_1", "SHARE_20_4"]
    rng_seed: int = 20260915
    auto_add_to_pool: bool = False


class ResetRosterBody(BaseModel):
    headcount: int = Field(default=5, ge=1, le=20)


def register_demo(app, get_db):
    @app.get("/api/demo/rehearsal")
    def rehearsal_script(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
        _role(x_demo_role)
        return {
            "code": 0,
            "message": "",
            "data": {
                "acts": acts_for_api(),
                "loop_acts": loop_acts_for_api(),
                "scope": SCOPE_SUMMARY,
            },
        }

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

    @app.get("/api/demo/scenario/status")
    def demo_scenario_status(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {"code": 0, "message": "", "data": scenario_status(db)}

    @app.post("/api/demo/scenario/reset-orders")
    def demo_reset_orders(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        stats = reset_order_scenario(db)
        audit_scenario(db, role=role, action="reset-orders", after=stats)
        return {"code": 0, "message": "已清空订单/排产/库存数量，产品维表保留", "data": stats}

    @app.post("/api/demo/scenario/reset-roster")
    def demo_reset_roster(
        body: ResetRosterBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        try:
            stats = apply_roster(db, headcount=body.headcount)
        except ScenarioPlanError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_scenario(db, role=role, action="reset-roster", after=stats)
        return {"code": 0, "message": f"已按每组 {body.headcount} 人重建花名册与产能", "data": stats}

    @app.post("/api/demo/scenario/preview-orders")
    def demo_preview_orders(
        body: GenerateOrdersBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        try:
            plan = plan_orders(
                body.order_count,
                DueMode(body.due_mode),
                ItemShareMode(body.item_share),
                rng_seed=body.rng_seed,
            )
        except ScenarioPlanError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"code": 0, "message": "", "data": plan_to_api(plan)}

    @app.post("/api/demo/scenario/generate-orders")
    def demo_generate_orders(
        body: GenerateOrdersBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        try:
            data = generate_orders(
                db,
                order_count=body.order_count,
                due_mode=body.due_mode,
                item_share=body.item_share,
                rng_seed=body.rng_seed,
                auto_add_to_pool=body.auto_add_to_pool,
            )
        except ScenarioPlanError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        audit_scenario(db, role=role, action="generate-orders", after={"order_count": data["order_count"]})
        return {"code": 0, "message": f"已生成 {data['order_count']} 张待排程订单", "data": data}

    @app.post("/api/demo/scenario/restore-seed")
    def demo_restore_seed(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        data = restore_official_seed(db)
        audit_scenario(db, role=role, action="restore-seed", after=data)
        return {"code": 0, "message": "已恢复官方 12 单种子", "data": data}
