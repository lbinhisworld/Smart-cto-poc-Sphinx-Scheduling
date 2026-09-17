"""FastAPI 路由（§9）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from api.schemas import (
    ApiResponse,
    CellDetailBody,
    StockPatchBody,
    InsertApplyBody,
    InsertTrialBody,
    InteractivePreviewBody,
    OrderCreate,
    OrderDuePatch,
    PublishPoolBody,
    SchedulingPoolBody,
    ScheduleBody,
)
from db.cell_detail_service import resolve_cell_detail
from db.plan_store import current_plan_version, load_schedule_result
from db.repositories import (
    apply_insert_strategy,
    create_order,
    get_order_due_date,
    list_orders,
    run_insert_trial,
    run_schedule,
    update_order_due_date_by_user,
)
from db.seed import import_seed_json
from engine.models import InsertStrategy, Order, ScheduleResult, Uom, WoTask

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "seed" / "seed_data.json"
from engine.diff import diff

logger = logging.getLogger(__name__)


def create_app(session_factory: sessionmaker) -> FastAPI:
    app = FastAPI(title="斯芬克斯一体化 POC")

    @app.exception_handler(OperationalError)
    async def db_operational_error(_request: Request, exc: OperationalError):
        logger.exception("database error")
        msg = str(exc.orig) if exc.orig else str(exc)
        hint = "数据库结构过旧：请重启后端（会自动迁移），或删除 data/scheduling.db 后重启。"
        if "conflicts_json" in msg:
            hint = "缺少 conflicts_json 列：重启后端以自动迁移，或删除 data/scheduling.db 后重启。"
        return JSONResponse(
            status_code=500,
            content={"code": 5001, "data": None, "message": f"{hint} ({msg[:200]})"},
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error(_request: Request, exc: SQLAlchemyError):
        logger.exception("sqlalchemy error")
        return JSONResponse(
            status_code=500,
            content={"code": 5002, "data": None, "message": str(exc)[:300]},
        )

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception):
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={"code": 5000, "data": None, "message": str(exc)[:300]},
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5180", "http://127.0.0.1:5180"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db() -> Session:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ok(data=None, message: str = "") -> ApiResponse:
        return ApiResponse(code=0, data=data, message=message)

    @app.get("/api/stock")
    def list_stock(db: Session = Depends(get_db)):
        from db.stock_repository import list_stock_rows

        rows = list_stock_rows(db)
        return ok(
            {
                "items": rows,
                "db_file": db.bind.url.database if db.bind else "",
                "provider_note": "POC 本地可改；生产由 ERP 只读同步",
            }
        )

    @app.patch("/api/stock/{item_code}")
    def patch_stock(item_code: str, body: StockPatchBody, db: Session = Depends(get_db)):
        from db.stock_repository import update_stock_qty

        row = update_stock_qty(db, item_code, Decimal(str(body.qty_available)), source="LOCAL")
        if row is None:
            raise HTTPException(status_code=404, detail="品项无库存记录")
        return ok(row)

    @app.post("/api/stock/sync-erp-mock")
    def sync_stock_erp_mock(
        mode: str = "merge",
        db: Session = Depends(get_db),
    ):
        from integrations.stock_provider import MockErpStockProvider
        from db.stock_repository import bulk_upsert_stock

        provider = MockErpStockProvider()
        entries, as_of = provider.fetch_entries()
        n = bulk_upsert_stock(db, entries, source="ERP_MOCK", mode=mode)
        return ok({"synced": n, "as_of": as_of.isoformat(), "mode": mode})

    @app.get("/api/plan/kit-status")
    def get_plan_kit_status(version: int | None = None, db: Session = Depends(get_db)):
        ver = version or current_plan_version(db)
        if ver <= 0:
            return ok({"plan_version": 0, "kit_checks": [], "kit_allocations": []})
        result = load_schedule_result(db, ver)
        return ok(
            {
                "plan_version": ver,
                "kit_checks": [k.model_dump(mode="json") for k in result.kit_checks],
                "kit_allocations": [a.model_dump(mode="json") for a in result.kit_allocations],
            }
        )

    @app.get("/api/health")
    def health():
        return ok(
            {
                "status": "ok",
                "features": {"bom": True, "schedule": True, "interactive_preview": True},
            }
        )

    @app.post("/api/schedule/run")
    def schedule_run(body: ScheduleBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        result, version, run_id = run_schedule(
            db,
            today=body.today,
            order_nos=body.order_nos,
            reserved_ratio=reserved,
            persist=True,
            trigger="初始排产",
        )
        return ok(
            {
                "plan_version": version,
                "run_id": run_id,
                "result": result.model_dump(mode="json"),
            }
        )

    @app.post("/api/schedule/interactive-preview")
    def schedule_interactive_preview(body: InteractivePreviewBody, db: Session = Depends(get_db)):
        from db.interactive_preview import run_interactive_preview

        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        data = run_interactive_preview(
            db,
            today=body.today,
            order_nos=body.order_nos,
            baseline_wos=body.baseline_wos,
            baseline_tasks=body.baseline_tasks,
            proposed_wos=body.proposed_wos,
            proposed_tasks=body.proposed_tasks,
            trigger_task_id=body.trigger_task_id,
            reserved_ratio=reserved,
        )
        return ok(data)

    @app.post("/api/schedule/what-if")
    def schedule_what_if(body: ScheduleBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        version_before = current_plan_version(db)
        result, _, run_id = run_schedule(
            db,
            today=body.today,
            order_nos=body.order_nos,
            reserved_ratio=reserved,
            persist=False,
            trigger="试排",
        )
        version_after = current_plan_version(db)
        return ok(
            {
                "plan_version": version_after,
                "plan_version_unchanged": version_after == version_before,
                "run_id": run_id,
                "result": result.model_dump(mode="json"),
            }
        )

    @app.post("/api/schedule/apply")
    def schedule_apply(body: ScheduleBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        result, version, run_id = run_schedule(
            db,
            today=body.today,
            order_nos=body.order_nos,
            reserved_ratio=reserved,
            persist=True,
            trigger="改单",
        )
        return ok(
            {
                "plan_version": version,
                "run_id": run_id,
                "result": result.model_dump(mode="json"),
            }
        )

    @app.get("/api/schedule/logs")
    def list_schedule_logs(limit: int = 50):
        from db.schedule_run_log import list_schedule_run_logs

        return ok({"logs": list_schedule_run_logs(limit=min(max(limit, 1), 200))})

    @app.get("/api/schedule/logs/{run_id}")
    def get_schedule_log(run_id: str, brief: bool = False):
        from db.schedule_run_log import load_schedule_run_log

        payload = load_schedule_run_log(run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="运行日志不存在")
        if brief:
            return ok({"run_id": run_id, "llm_brief": payload.get("llm_brief", "")})
        return ok(payload)

    @app.get("/api/plan")
    def get_plan(version: int | None = None, db: Session = Depends(get_db)):
        ver = version or current_plan_version(db)
        if ver <= 0:
            raise HTTPException(status_code=404, detail="尚无计划版本")
        result = load_schedule_result(db, ver)
        return ok({"plan_version": ver, "result": result.model_dump(mode="json")})

    @app.get("/api/plan/cell-detail")
    def get_plan_cell_detail(
        today: date,
        dept: str,
        group_code: str,
        task_date: date,
        focus_task_id: int | None = None,
        version: int | None = None,
        db: Session = Depends(get_db),
    ):
        try:
            detail = resolve_cell_detail(
                db,
                today=today,
                dept=dept,
                group_code=group_code,
                task_date=task_date,
                focus_task_id=focus_task_id,
                plan_version=version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return ok(detail)

    @app.post("/api/plan/cell-detail")
    def post_plan_cell_detail(body: CellDetailBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        override = ScheduleResult.model_validate(body.result) if body.result else None
        tasks_override = (
            [WoTask.model_validate(row) for row in body.tasks] if body.tasks else None
        )
        try:
            detail = resolve_cell_detail(
                db,
                today=body.today,
                dept=body.dept,
                group_code=body.group_code,
                task_date=body.task_date,
                focus_task_id=body.focus_task_id,
                plan_version=body.plan_version,
                result_override=override,
                tasks_override=tasks_override,
                reserved_ratio=reserved,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        return ok(detail)

    @app.get("/api/plan/diff")
    def get_plan_diff(from_version: int, to_version: int, today: date, db: Session = Depends(get_db)):
        base = load_schedule_result(db, from_version)
        new = load_schedule_result(db, to_version)
        d = diff(base, new, today)
        return ok({"diff": d.model_dump(mode="json")})

    @app.get("/api/conflicts")
    def get_conflicts(version: int | None = None, db: Session = Depends(get_db)):
        ver = version or current_plan_version(db)
        if ver <= 0:
            return ok({"conflicts": []})
        result = load_schedule_result(db, ver)
        return ok({"plan_version": ver, "conflicts": [c.model_dump(mode="json") for c in result.conflicts]})

    @app.post("/api/schedule/insert")
    def schedule_insert_trial(body: InsertTrialBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        try:
            compare = run_insert_trial(
                db,
                urgent_order_no=body.order_no,
                today=body.today,
                reserved_ratio=reserved,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="订单不存在") from None
        return ok(
            {
                "feasibility": compare.feasibility.model_dump(mode="json"),
                "diff": compare.diff.model_dump(mode="json"),
                "strategies": [
                    {
                        "strategy": s.strategy.value,
                        "diff": s.diff.model_dump(mode="json"),
                    }
                    for s in compare.strategies
                ],
            }
        )

    @app.post("/api/schedule/insert/apply")
    def schedule_insert_apply(body: InsertApplyBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        try:
            strategy = InsertStrategy(body.strategy)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效策略") from None
        try:
            result, version = apply_insert_strategy(
                db,
                urgent_order_no=body.order_no,
                today=body.today,
                strategy=strategy,
                reason=body.reason,
                requester=body.requester,
                reserved_ratio=reserved,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="订单不存在") from None
        except StopIteration:
            raise HTTPException(status_code=400, detail="策略结果缺失") from None
        return ok({"plan_version": version, "result": result.model_dump(mode="json")})

    @app.post("/api/orders/scheduling-pool")
    def post_scheduling_pool(body: SchedulingPoolBody, db: Session = Depends(get_db)):
        from db.order_lifecycle import (
            add_to_scheduling_pool,
            remove_from_scheduling_pool,
            scheduling_pool_order_nos,
        )

        try:
            if body.action == "remove":
                remove_from_scheduling_pool(db, body.order_nos)
            else:
                add_to_scheduling_pool(db, body.order_nos)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"订单不存在: {exc}") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        db.flush()
        return ok({"pool": scheduling_pool_order_nos(db)})

    @app.post("/api/orders/publish")
    def post_publish_pool(body: PublishPoolBody, db: Session = Depends(get_db)):
        from db.order_lifecycle import (
            PublishBlockedError,
            commitments_for_orders,
            publish_scheduling_pool,
            scheduling_pool_order_nos,
        )

        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        pool = body.order_nos or scheduling_pool_order_nos(db)
        try:
            result, version, commits = publish_scheduling_pool(
                db,
                today=body.today,
                order_nos=pool,
                reserved_ratio=reserved,
                force_red=body.force_red,
            )
        except PublishBlockedError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "published": False,
                    "blocks": exc.blocks,
                    "commitments": commitments_for_orders(exc.result, pool),
                    "result": exc.result.model_dump(mode="json"),
                },
            ) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        db.flush()
        return ok(
            {
                "published": True,
                "plan_version": version,
                "commitments": commits,
                "result": result.model_dump(mode="json"),
            }
        )

    @app.get("/api/orders")
    def get_orders(db: Session = Depends(get_db)):
        from db.master_data import route_summary_for_item
        from db.seed import count_orders, ensure_seed_current

        sync = ensure_seed_current(db, SEED_PATH)
        db.flush()
        orders = list_orders(db)
        rows = []
        for o in orders:
            route = route_summary_for_item(db, o.item_code)
            rows.append(
                {
                    **o.model_dump(mode="json"),
                    "qty_order": float(o.qty_order),
                    "amount": float(o.amount),
                    "bom_route": route,
                }
            )
        return ok(
            {
                "orders": rows,
                "seed_sync": sync,
                "orders_in_db": count_orders(db),
                "db_file": db.bind.url.database if db.bind else "",
            }
        )

    @app.post("/api/orders")
    def post_order(body: OrderCreate, db: Session = Depends(get_db)):
        order = Order(
            order_no=body.order_no,
            customer=body.customer,
            sales_name=body.sales_name,
            item_code=body.item_code,
            qty_order=Decimal(str(body.qty_order)),
            unit=Uom(body.unit),
            due_date=body.due_date,
            ready_date=body.ready_date,
            customer_level=body.customer_level,
            amount=Decimal(str(body.amount)),
            is_urgent=body.is_urgent,
        )
        try:
            create_order(db, order)
        except Exception as exc:
            raise HTTPException(status_code=409, detail="订单已存在") from exc
        return ok({"order_no": order.order_no})

    @app.get("/api/dev/seed-status")
    def dev_seed_status(db: Session = Depends(get_db)):
        from db.seed import count_orders, needs_seed_reload, seed_manifest

        manifest = seed_manifest(SEED_PATH)
        return ok(
            {
                **manifest,
                "needs_reload": needs_seed_reload(db, SEED_PATH),
                "orders_in_db": count_orders(db),
                "seed_path": str(SEED_PATH),
                "db_file": db.bind.url.database if db.bind else "",
            }
        )

    @app.post("/api/dev/import-seed")
    def dev_import_seed(db: Session = Depends(get_db)):
        from db.seed import count_orders, reload_seed_json

        manifest = reload_seed_json(db, SEED_PATH)
        db.flush()
        return ok(
            {
                "seed": str(SEED_PATH),
                "orders_in_db": count_orders(db),
                "db_file": db.bind.url.database if db.bind else "",
                **manifest,
            }
        )

    # 静态路径 /scheduling-pool、/publish 必须单独注册；否则 POST 会落到本路由并 405。
    @app.patch("/api/orders/{order_no}")
    def patch_order_due(order_no: str, body: OrderDuePatch, db: Session = Depends(get_db)):
        try:
            update_order_due_date_by_user(db, order_no, body.due_date)
        except KeyError:
            raise HTTPException(status_code=404, detail="订单不存在") from None
        return ok({"order_no": order_no, "due_date": body.due_date.isoformat()})

    @app.get("/api/orders/{order_no}")
    def get_order(order_no: str, db: Session = Depends(get_db)):
        try:
            due = get_order_due_date(db, order_no)
        except KeyError:
            raise HTTPException(status_code=404, detail="订单不存在") from None
        return ok({"order_no": order_no, "due_date": due.isoformat()})

    @app.get("/api/bom")
    def get_bom_catalog(db: Session = Depends(get_db)):
        from db.bom_view import bom_catalog
        from db.seed import ensure_seed_current

        ensure_seed_current(db, SEED_PATH)
        db.flush()
        return ok(bom_catalog(db, SEED_PATH))

    @app.get("/api/bom/explode")
    def get_bom_explode(
        item_code: str,
        qty: float,
        unit: str = "BOX",
        today: date | None = None,
        db: Session = Depends(get_db),
    ):
        from db.bom_view import bom_explode
        from db.seed import ensure_seed_current

        ensure_seed_current(db, SEED_PATH)
        db.flush()
        result = bom_explode(
            db,
            item_code,
            Decimal(str(qty)),
            unit,
            today=today or date.fromisoformat("2026-09-15"),
        )
        if result is None:
            raise HTTPException(status_code=404, detail="品项不存在") from None
        return ok(result)

    @app.get("/api/bom/{item_code}")
    def get_bom_design(item_code: str, db: Session = Depends(get_db)):
        from db.bom_view import bom_design
        from db.seed import ensure_seed_current

        ensure_seed_current(db, SEED_PATH)
        db.flush()
        design = bom_design(db, item_code)
        if design is None:
            raise HTTPException(status_code=404, detail="品项不存在") from None
        return ok(design)

    from apps.api.routers.changes import register_changes
    from apps.api.routers.due_negotiate import register_due_negotiate
    from apps.api.routers.cockpit import register_cockpit
    from apps.api.routers.hr import register_hr
    from apps.api.routers.labor import register_labor
    from apps.api.routers.demo import register_demo
    from apps.api.routers.crm import register_crm
    from apps.api.routers.kingdee import register_kingdee
    from apps.api.routers.mis import register_mis
    from apps.api.routers.portal import router as portal_router
    from apps.api.routers.wecom import register_wecom
    from db.dispatch_export import build_dispatch_workbook_bytes
    from fastapi.responses import Response

    @app.get("/api/plan/export-dispatch")
    def export_dispatch(db: Session = Depends(get_db)):
        data = build_dispatch_workbook_bytes(db)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="dispatch.xlsx"'},
        )

    app.include_router(portal_router)
    register_mis(app, get_db)
    register_kingdee(app, get_db)
    register_crm(app, get_db)
    register_changes(app, get_db)
    register_due_negotiate(app, get_db)
    register_wecom(app, get_db)
    register_cockpit(app, get_db)
    register_hr(app, get_db)
    register_labor(app, get_db)
    register_demo(app, get_db)
    from apps.api.routers.qc import register_qc

    register_qc(app, get_db)

    return app
