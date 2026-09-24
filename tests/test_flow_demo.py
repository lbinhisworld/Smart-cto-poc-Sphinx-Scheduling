"""派工演示四单：生成、只排两张、测试报工留尾数。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select

from db.flow_demo import seed_flow_demo, scripted_labor_report
from db.repositories import run_schedule
from db.schedule_progress import schedule_progress
from db.seed import import_seed_json, needs_seed_reload, reload_seed_json
from db.tables import SoOrderRow

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "seed_data.json"
DB = ROOT / "data" / "scheduling_test_flow_demo.db"


@pytest.fixture()
def db_session():
    from db.migrate import ensure_schema
    from db.session import init_db, make_engine, session_factory

    if DB.is_file():
        DB.unlink()
    engine = make_engine(DB)
    init_db(engine)
    ensure_schema(engine)
    factory = session_factory(engine)
    session = factory()
    if needs_seed_reload(session, SEED):
        reload_seed_json(session, SEED)
    else:
        import_seed_json(session, SEED)
    session.commit()
    yield session
    session.close()
    if DB.is_file():
        DB.unlink()


def test_flow_orders_are_pending_and_dues_stay(db_session):
    data = seed_flow_demo(db_session)
    db_session.commit()
    rows = {r.order_no: r for r in db_session.scalars(select(SoOrderRow)).all()}
    assert set(rows) == {"FLOW-OK", "FLOW-SHORT", "FLOW-HOLD", "FLOW-CAP"}
    assert all(r.schedule_phase == "PENDING" for r in rows.values())
    assert rows["FLOW-OK"].due_date == date(2026, 9, 25)
    assert rows["FLOW-CAP"].due_date == date(2026, 9, 17)
    assert data["pool"] == ["FLOW-OK", "FLOW-SHORT"]
    assert data["leave_out"] == ["FLOW-HOLD", "FLOW-CAP"]


def test_scripted_report_leaves_remainder_and_unscheduled(db_session):
    seed_flow_demo(db_session)
    dues = {
        r.order_no: r.due_date
        for r in db_session.scalars(select(SoOrderRow)).all()
    }
    run_schedule(
        db_session,
        today=date(2026, 9, 15),
        order_nos=["FLOW-OK", "FLOW-SHORT"],
        persist=True,
        trigger="flow-demo",
    )
    db_session.commit()
    out = scripted_labor_report(db_session, today=date(2026, 9, 15), reported_by="演示")
    db_session.commit()
    by_no = {r["order_no"]: r for r in out["reports"]}
    assert by_no["FLOW-OK"]["qty_board_remain"] == 0
    assert by_no["FLOW-SHORT"]["qty_board_remain"] > 0
    assert by_no["FLOW-SHORT"]["roll"]["status"] == "PENDING_CONFIRMATION"
    after = {r.order_no: r.due_date for r in db_session.scalars(select(SoOrderRow)).all()}
    assert after == dues

    progress = schedule_progress(db_session)
    not_placed = {r["order_no"] for r in progress["not_placed"]}
    assert "FLOW-HOLD" in not_placed
    assert "FLOW-CAP" in not_placed
    assert "FLOW-OK" not in not_placed
    partial = {r["order_no"] for r in progress["partial"]}
    assert "FLOW-SHORT" in partial
