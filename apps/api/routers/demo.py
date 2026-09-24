"""Phase 8：演示控制台 + 待办中心 + 场景台。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.demo_system_reset import reset_demo_system
from db.guided_demo_step_apply import compact_apply_user_message
from db.guided_demo_runs import (
    GuidedDemoError,
    add_feedback,
    create_run,
    continue_run,
    delete_run,
    end_replay,
    end_run,
    export_markdown,
    get_active_run,
    get_run,
    guided_context_for_path,
    list_feedback,
    list_runs,
    path_catalog,
    saved_step_data,
    seed_step,
    set_current_step,
    start_replay,
    start_run,
    step_readiness,
)
from shared.guided_demo_path import next_step_id

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


class CreateDemoRunBody(BaseModel):
    title: str = Field(default="", max_length=120)


class DemoFeedbackBody(BaseModel):
    step_id: str
    category: str = Field(default="其他")
    severity: str = Field(default="会后优化")
    body: str
    expectation: str = ""
    story_index: int | None = None
    seed_event_id: int | None = None
    refs: list[dict] = Field(default_factory=list)


class AdvanceStepBody(BaseModel):
    step_id: str | None = None


def _guided_error(exc: GuidedDemoError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


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

    @app.post("/api/demo/scenario/flow-orders")
    def demo_flow_orders(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        from db.flow_demo import seed_flow_demo

        data = seed_flow_demo(db)
        audit_scenario(db, role=role, action="flow-orders", after={"orders": [o["order_no"] for o in data["orders"]]})
        return {"code": 0, "message": "已生成派工演示四单，现有订单和计划已清空", "data": data}

    @app.get("/api/demo/guided/path")
    def demo_guided_path(x_demo_role: str | None = Header(default=None, alias="X-Demo-Role")):
        _role(x_demo_role)
        return {"code": 0, "message": "", "data": path_catalog()}

    @app.get("/api/demo/guided/context")
    def demo_guided_context(
        path: str = Query(..., min_length=1),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        ctx = guided_context_for_path(db, path)
        return {"code": 0, "message": "", "data": ctx}

    @app.post("/api/demo/system/reset")
    def demo_system_reset(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        stats = reset_demo_system(db)
        audit_scenario(db, role=role, action="system-reset", after=stats)
        return {
            "code": 0,
            "message": "已重置系统：全部数据已清空；后续请用演示线「生成数据」或各模块手工录入",
            "data": stats,
        }

    @app.get("/api/demo/runs")
    def demo_runs_list(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {"code": 0, "message": "", "data": {"items": list_runs(db)}}

    @app.get("/api/demo/runs/active")
    def demo_runs_active(
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        return {"code": 0, "message": "", "data": get_active_run(db)}

    @app.post("/api/demo/runs")
    def demo_runs_create(
        body: CreateDemoRunBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        try:
            data = create_run(db, title=body.title, role=role)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "已创建演示线", "data": data}

    @app.get("/api/demo/runs/{run_id}")
    def demo_runs_get(
        run_id: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        data = get_run(db, run_id)
        if data is None:
            raise HTTPException(status_code=404, detail="演示线不存在")
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/demo/runs/{run_id}/continue")
    def demo_runs_continue(
        run_id: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        try:
            data = continue_run(db, run_id, role=role)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {
            "code": 0,
            "message": "已恢复演示线，请在本页继续操作",
            "data": data,
        }

    @app.post("/api/demo/runs/{run_id}/start")
    def demo_runs_start(
        run_id: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        try:
            data = start_run(db, run_id, role=role)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "演示线已开始", "data": data}

    @app.post("/api/demo/runs/{run_id}/end")
    def demo_runs_end(
        run_id: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        try:
            data = end_run(db, run_id, role=role)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "演示线已结束，环节数据已归档", "data": data}

    @app.delete("/api/demo/runs/{run_id}")
    def demo_runs_delete(
        run_id: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        try:
            data = delete_run(db, run_id, role=role)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "已删除演示线", "data": data}

    @app.post("/api/demo/runs/{run_id}/replay")
    def demo_runs_replay(
        run_id: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        _require_gm(role)
        try:
            data = start_replay(db, run_id, role=role)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "已进入重放模式（只读数据，可继续反馈）", "data": data}

    @app.post("/api/demo/runs/{run_id}/replay/end")
    def demo_runs_replay_end(
        run_id: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        try:
            data = end_replay(db, run_id, role=role)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "已退出重放", "data": data}

    @app.get("/api/demo/runs/{run_id}/feedback")
    def demo_runs_feedback_list(
        run_id: str,
        step_id: str | None = Query(default=None),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        items = list_feedback(db, run_id, step_id=step_id)
        return {"code": 0, "message": "", "data": {"items": items}}

    @app.get("/api/demo/guided/step/{step_id}/saved")
    def demo_guided_saved(
        step_id: str,
        run_id: str = Query(...),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        data = saved_step_data(db, run_id, step_id)
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/demo/guided/step/{step_id}/readiness")
    def demo_guided_readiness(
        step_id: str,
        run_id: str = Query(...),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        try:
            data = step_readiness(db, run_id, step_id)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "", "data": data}

    @app.post("/api/demo/guided/step/{step_id}/seed")
    def demo_guided_seed(
        step_id: str,
        run_id: str = Query(...),
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        try:
            data = seed_step(db, run_id, step_id, role=role)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        apply = data.get("apply") or {}
        message = (
            compact_apply_user_message(step_id, apply)
            if apply.get("applied")
            else (data.get("summary") or "已生成本环节数据")
        )
        return {"code": 0, "message": message, "data": data}

    @app.post("/api/demo/runs/{run_id}/feedback")
    def demo_runs_feedback(
        run_id: str,
        body: DemoFeedbackBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        role = _role(x_demo_role)
        try:
            data = add_feedback(
                db,
                run_id,
                step_id=body.step_id,
                category=body.category,
                severity=body.severity,
                body=body.body,
                expectation=body.expectation,
                story_index=body.story_index,
                seed_event_id=body.seed_event_id,
                refs=body.refs,
                role=role,
            )
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "已记录反馈", "data": data}

    @app.post("/api/demo/runs/{run_id}/advance")
    def demo_runs_advance(
        run_id: str,
        body: AdvanceStepBody,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        row = get_run(db, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="演示线不存在")
        if not row.get("is_active") and not row.get("is_replay"):
            raise HTTPException(status_code=400, detail="请先启动演示线或进入重放")
        target = body.step_id
        if not target:
            cur = row.get("current_step_id")
            if not cur:
                raise HTTPException(status_code=400, detail="无当前环节")
            target = next_step_id(cur)
            if not target:
                raise HTTPException(status_code=400, detail="已在最后一步")
        try:
            data = set_current_step(db, run_id, target)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return {"code": 0, "message": "", "data": data}

    @app.get("/api/demo/runs/{run_id}/export.md")
    def demo_runs_export_md(
        run_id: str,
        x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
        db: Session = Depends(get_db),
    ):
        _role(x_demo_role)
        try:
            md = export_markdown(db, run_id)
        except GuidedDemoError as exc:
            raise _guided_error(exc) from exc
        return Response(content=md, media_type="text/markdown; charset=utf-8")
