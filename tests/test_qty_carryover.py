"""Wave 2：报工完工版数 → 待确认池；PMC 合并或插单，禁止自动重排 / 取消尾数。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api.main import create_app
from db.qty_carryover import (
    ACTION_CANCEL,
    ACTION_INSERT,
    ACTION_MERGE,
    confirm_wo_qty,
    list_pending_rolls,
    resolve_roll,
    wo_qty_progress,
)
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from db.tables import PlanVersionRow, SoOrderRow, WoRow, WoTaskRow
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TODAY = date(2026, 9, 15)
DUE = date(2026, 10, 1)
HDR_PMC = {"X-Demo-Role": "PMC"}


@pytest.fixture
def carry_db(tmp_path):
    engine = make_engine(tmp_path / "carry.db")
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, ROOT / "seed" / "seed_data.json")
        session.commit()
        _plant_wo(session, qty_plan=100)
        session.commit()
    finally:
        session.close()
    app = create_app(factory)
    with TestClient(app) as client:
        yield client, factory


def _plant_wo(session, *, qty_plan: int = 100, extra_same_item: bool = False) -> None:
    session.add(
        SoOrderRow(
            order_no="SO-T1",
            customer="尾数测试客户",
            sales_name="测试",
            item_code="P1",
            qty_order=str(qty_plan),
            unit="BOARD",
            due_date=DUE,
            customer_level=3,
            amount="0",
            is_urgent=False,
            schedule_phase="IN_PRODUCTION",
            order_source="TEST",
        )
    )
    session.add(
        PlanVersionRow(
            created_at=datetime(2026, 9, 15, 8, 0, 0),
            trigger="测试种植",
            snapshot_hash="",
            conflicts_json="[]",
            kit_json="{}",
        )
    )
    session.flush()
    session.add(
        WoRow(
            wo_no="WO-SO-T1-1",
            wo_type="FINISHED",
            source_order_no="SO-T1",
            item_code="P1",
            group_code="MANUAL",
            dept="FINISHED_DEPT",
            qty_order=str(qty_plan),
            qty_board_plan=qty_plan,
            due_date=DUE,
            plan_start=date(2026, 9, 25),
            plan_end=date(2026, 9, 25),
            earliest_start=TODAY,
            crew_plan=3,
            status="RELEASED",
            plan_version=1,
        )
    )
    session.add(
        WoTaskRow(
            wo_no="WO-SO-T1-1",
            dept="FINISHED_DEPT",
            group_code="MANUAL",
            task_date=date(2026, 9, 25),
            qty_board=qty_plan,
            hours_wall="8",
            hours_man="24",
            crew_plan=3,
            seq=1,
            plan_version=1,
        )
    )
    if extra_same_item:
        session.add(
            SoOrderRow(
                order_no="SO-T2",
                customer="并入目标",
                sales_name="测试",
                item_code="P1",
                qty_order="40",
                unit="BOARD",
                due_date=date(2026, 10, 8),
                customer_level=3,
                amount="0",
                is_urgent=False,
                schedule_phase="PENDING",
                order_source="TEST",
            )
        )


def _task_count(session, wo_no: str | None = None) -> int:
    q = select(func.count()).select_from(WoTaskRow)
    if wo_no:
        q = q.where(WoTaskRow.wo_no == wo_no)
    return int(session.scalar(q) or 0)


def test_confirm_80_of_100_enters_pool_without_auto_schedule(carry_db):
    _client, factory = carry_db
    session = factory()
    try:
        before_tasks = _task_count(session)
        before_ver = session.scalar(select(func.max(PlanVersionRow.version_no)))
        out = confirm_wo_qty(
            session,
            wo_no="WO-SO-T1-1",
            qty_board_done=80,
            reported_by="测试班长",
            work_date=date(2026, 9, 25),
        )
        session.commit()

        assert out["qty_board_plan"] == 100
        assert out["qty_board_done"] == 80
        assert out["qty_board_remain"] == 20
        assert out["wo_status"] == "PARTIAL"
        assert out["roll"]["status"] == "PENDING_CONFIRMATION"
        assert out["roll"]["qty_board_remain"] == 20

        prog = wo_qty_progress(session, "WO-SO-T1-1")
        assert prog["qty_board_remain"] == 20

        rolls = list_pending_rolls(session)
        assert len(rolls) == 1
        assert rolls[0]["qty_board_remain"] == 20
        assert rolls[0]["status"] == "PENDING_CONFIRMATION"

        wo = session.get(WoRow, "WO-SO-T1-1")
        assert wo is not None
        assert wo.status == "PARTIAL"
        assert wo.qty_board_done == 80

        order = session.get(SoOrderRow, "SO-T1")
        assert order is not None
        assert order.due_date == DUE
        assert order.schedule_phase == "IN_PRODUCTION"

        assert _task_count(session) == before_tasks
        assert session.scalar(select(func.max(PlanVersionRow.version_no))) == before_ver
        assert _task_count(session, "WO-SO-T1-1") == 1
    finally:
        session.close()


def test_br27_qty_confirm_does_not_write_due_date(carry_db):
    _client, factory = carry_db
    session = factory()
    try:
        confirm_wo_qty(session, wo_no="WO-SO-T1-1", qty_board_done=80, reported_by="x")
        session.commit()
        assert session.get(SoOrderRow, "SO-T1").due_date == DUE
    finally:
        session.close()


def test_reject_cancel_remainder(carry_db):
    _client, factory = carry_db
    session = factory()
    try:
        confirm_wo_qty(session, wo_no="WO-SO-T1-1", qty_board_done=80, reported_by="x")
        session.commit()
        rid = list_pending_rolls(session)[0]["id"]
        with pytest.raises(ValueError, match="取消尾数"):
            resolve_roll(
                session,
                roll_id=rid,
                action=ACTION_CANCEL,
                today=TODAY,
                resolved_by="PMC",
            )
    finally:
        session.close()


def test_pmc_insert_schedules_only_remain_20(carry_db):
    _client, factory = carry_db
    session = factory()
    try:
        confirm_wo_qty(session, wo_no="WO-SO-T1-1", qty_board_done=80, reported_by="x")
        session.commit()
        before_orig_tasks = _task_count(session, "WO-SO-T1-1")
        rid = list_pending_rolls(session)[0]["id"]
        resolved = resolve_roll(
            session,
            roll_id=rid,
            action=ACTION_INSERT,
            today=TODAY,
            resolved_by="PMC",
        )
        session.commit()

        assert resolved["status"] == "INSERTED"
        rem_wo_no = resolved["remainder_wo_no"]
        rem = session.get(WoRow, rem_wo_no)
        assert rem is not None
        assert rem.qty_board_plan == 20
        placed = sum(
            t.qty_board
            for t in session.scalars(select(WoTaskRow).where(WoTaskRow.wo_no == rem_wo_no)).all()
        )
        assert placed == 20
        assert _task_count(session, "WO-SO-T1-1") == before_orig_tasks

        orig = session.get(WoRow, "WO-SO-T1-1")
        assert orig.qty_board_done == 80
        assert orig.qty_board_plan == 100
        assert orig.status == "PARTIAL"
        assert session.get(SoOrderRow, "SO-T1").due_date == DUE
        rem_order = session.get(SoOrderRow, resolved["remainder_order_no"])
        assert rem_order is not None
        assert rem_order.due_date == DUE
        assert rem_order.qty_order == Decimal("20") or str(rem_order.qty_order) in {"20", "20.0000"}
    finally:
        session.close()


def test_pmc_merge_adds_20_to_next_same_item_without_reschedule(carry_db):
    _client, factory = carry_db
    session = factory()
    try:
        session.add(
            SoOrderRow(
                order_no="SO-T2",
                customer="并入目标",
                sales_name="测试",
                item_code="P1",
                qty_order="40",
                unit="BOARD",
                due_date=date(2026, 10, 8),
                customer_level=3,
                amount="0",
                is_urgent=False,
                schedule_phase="PENDING",
                order_source="TEST",
            )
        )
        session.commit()
        confirm_wo_qty(session, wo_no="WO-SO-T1-1", qty_board_done=80, reported_by="x")
        session.commit()
        before_ver = session.scalar(select(func.max(PlanVersionRow.version_no)))
        before_tasks = _task_count(session)
        rid = list_pending_rolls(session)[0]["id"]
        resolved = resolve_roll(
            session,
            roll_id=rid,
            action=ACTION_MERGE,
            today=TODAY,
            resolved_by="PMC",
            target_order_no="SO-T2",
        )
        session.commit()
        assert resolved["status"] == "MERGED"
        assert resolved["target_order_no"] == "SO-T2"
        target = session.get(SoOrderRow, "SO-T2")
        assert Decimal(str(target.qty_order)) == Decimal("60")
        assert target.due_date == date(2026, 10, 8)
        assert session.get(SoOrderRow, "SO-T1").due_date == DUE
        assert session.scalar(select(func.max(PlanVersionRow.version_no))) == before_ver
        assert _task_count(session) == before_tasks
    finally:
        session.close()


def test_qty_confirm_and_pool_api(carry_db):
    client, factory = carry_db
    conf = client.post(
        "/api/labor/wos/WO-SO-T1-1/qty-confirm",
        headers=HDR_PMC,
        json={"qty_board_done": 80, "work_date": "2026-09-25"},
    )
    assert conf.status_code == 200, conf.text
    body = conf.json()["data"]
    assert body["qty_board_remain"] == 20
    assert body["roll"]["status"] == "PENDING_CONFIRMATION"

    pool = client.get("/api/labor/qty-rolls", headers=HDR_PMC)
    assert pool.status_code == 200
    rows = pool.json()["data"]
    assert len(rows) == 1
    rid = rows[0]["id"]

    cancel = client.post(
        f"/api/labor/qty-rolls/{rid}/resolve",
        headers=HDR_PMC,
        json={"action": "CANCEL"},
    )
    assert cancel.status_code == 400

    todos = client.get("/api/demo/todos", headers=HDR_PMC)
    assert todos.status_code == 200
    kinds = {t["kind"] for t in todos.json()["data"]["items"]}
    assert "QTY_CARRYOVER" in kinds
