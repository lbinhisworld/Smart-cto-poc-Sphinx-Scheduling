"""FastAPI 路由（§9）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session, sessionmaker

from api.schemas import ApiResponse, OrderDuePatch, ScheduleBody
from db.plan_store import current_plan_version, load_schedule_result
from db.repositories import get_order_due_date, run_schedule, update_order_due_date_by_user
from engine.diff import diff


def create_app(session_factory: sessionmaker) -> FastAPI:
    app = FastAPI(title="斯芬克斯排程 POC")

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

    @app.get("/api/health")
    def health():
        return ok({"status": "ok"})

    @app.post("/api/schedule/run")
    def schedule_run(body: ScheduleBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        result, version = run_schedule(
            db,
            today=body.today,
            order_nos=body.order_nos,
            reserved_ratio=reserved,
            persist=True,
            trigger="初始排产",
        )
        return ok({"plan_version": version, "result": result.model_dump(mode="json")})

    @app.post("/api/schedule/what-if")
    def schedule_what_if(body: ScheduleBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        version_before = current_plan_version(db)
        result, _ = run_schedule(
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
                "result": result.model_dump(mode="json"),
            }
        )

    @app.post("/api/schedule/apply")
    def schedule_apply(body: ScheduleBody, db: Session = Depends(get_db)):
        reserved = Decimal(str(body.reserved_ratio if body.reserved_ratio is not None else 0))
        result, version = run_schedule(
            db,
            today=body.today,
            order_nos=body.order_nos,
            reserved_ratio=reserved,
            persist=True,
            trigger="改单",
        )
        return ok({"plan_version": version, "result": result.model_dump(mode="json")})

    @app.get("/api/plan")
    def get_plan(version: int | None = None, db: Session = Depends(get_db)):
        ver = version or current_plan_version(db)
        if ver <= 0:
            raise HTTPException(status_code=404, detail="尚无计划版本")
        result = load_schedule_result(db, ver)
        return ok({"plan_version": ver, "result": result.model_dump(mode="json")})

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

    return app
