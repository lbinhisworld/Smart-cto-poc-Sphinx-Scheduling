"""领料只读列：已领 / 待领 / 本次领，库存与需求只展示。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app_factory import app
from db.repositories import run_schedule
from db.seed import import_seed_json, needs_seed_reload, reload_seed_json
from db.session import session_factory
from db.tables import InvIssueRow

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "seed_data.json"
DB = ROOT / "data" / "scheduling_test_pick.db"

client = TestClient(app)
PMC = {"X-Demo-Role": "PMC"}


@pytest.fixture()
def db_session():
    from db.migrate import ensure_schema
    from db.session import init_db, make_engine

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


def test_pick_list_progress_empty_without_issue(db_session):
    from db.pick_list import build_pick_list

    run_schedule(
        db_session,
        today=date(2026, 9, 15),
        order_nos=["SO-001", "SO-002"],
        persist=True,
        trigger="pick-test",
    )
    db_session.commit()
    rows = build_pick_list(db_session)
    assert rows
    first = rows[0]
    assert "component_code" in first
    assert "day_qty" in first
    assert "gross_board" in first
    assert first["issued"] is None
    assert first["pending"] is None
    assert first["this_time"] is None
    assert "stock_board" in first
    assert "demand_board" in first
    assert first["demand_board"] == first["gross_board"]


def test_pick_list_fills_when_issue_recorded(db_session):
    from db.pick_list import build_pick_list

    run_schedule(
        db_session,
        today=date(2026, 9, 15),
        order_nos=["SO-001", "SO-002"],
        persist=True,
        trigger="pick-issue",
    )
    db_session.commit()
    rows = build_pick_list(db_session)
    target = next(row for row in rows if row["component_code"])
    db_session.add(
        InvIssueRow(
            work_date=date.fromisoformat(target["work_date"]),
            dest="INTERNAL",
            item_code=target["component_code"],
            qty_board=1,
            note="演示领料",
            created_by="测试",
        )
    )
    db_session.commit()
    after = [
        row
        for row in build_pick_list(db_session)
        if row["component_code"] == target["component_code"] and row["work_date"] == target["work_date"]
    ]
    assert after
    assert after[0]["this_time"] == 1
    assert after[0]["issued"] == 1
    assert after[0]["pending"] == max(0, after[0]["gross_board"] - 1)


def test_pick_list_api_does_not_change_due_date():
    before = client.get("/api/orders/SO-001", headers=PMC).json()["data"]["due_date"]
    r = client.get("/api/plan/pick-list", headers=PMC)
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "rows" in body
    assert client.get("/api/orders/SO-001", headers=PMC).json()["data"]["due_date"] == before
