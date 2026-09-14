"""阶段 4 HTTP 集成测试（httpx TestClient）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.plan_store import current_plan_version
from db.repositories import get_order_due_date
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from engine.models import ScheduleResult
from engine.schedule import schedule
from tests.conftest import ROOT, TODAY, build_schedule_input, load_seed
from tests.helpers import semi_wo_of, tasks_of


def _tasks_from_payload(payload: dict, item_code: str) -> list[tuple[str, int]]:
    wo_nos = {w["wo_no"] for w in payload["wos"] if w["item_code"] == item_code}
    rows = [
        (t["task_date"], t["qty_board"])
        for t in payload["tasks"]
        if t["wo_no"] in wo_nos
    ]
    return sorted(rows)


@pytest.fixture
def api_client(tmp_path):
    db_path = tmp_path / "api_test.db"
    engine = make_engine(db_path)
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, ROOT / "seed" / "seed_data.json")
        session.commit()
    finally:
        session.close()
    app = create_app(factory)
    with TestClient(app) as client:
        yield client, factory


def _run_body(order_nos=None):
    return {
        "order_nos": order_nos or ["SO-001", "SO-002", "SO-003"],
        "today": TODAY.isoformat(),
        "reserved_ratio": 0.0,
    }


def test_api_run_three_orders_matches_engine(api_client):
    client, _ = api_client
    resp = client.post("/api/schedule/run", json=_run_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["plan_version"] == 1

    payload = body["data"]["result"]
    seed = load_seed()
    expected = schedule(
        build_schedule_input(seed, today=TODAY, reserved_ratio=Decimal("0"))
    )
    for code in ("P1", "P2", "P4", "S2"):
        exp = [(d.isoformat(), q) for d, q in tasks_of(expected, code)]
        assert _tasks_from_payload(payload, code) == exp
    assert semi_wo_of(expected, "SO-002").qty_board_plan == 282


def test_api_what_if_does_not_bump_version(api_client):
    client, _ = api_client
    client.post("/api/schedule/run", json=_run_body())
    resp = client.post("/api/schedule/what-if", json=_run_body())
    data = resp.json()["data"]
    assert data["plan_version_unchanged"] is True
    assert data["plan_version"] == 1


def test_api_apply_bumps_plan_version(api_client):
    client, factory = api_client
    client.post("/api/schedule/run", json=_run_body())
    resp = client.post("/api/schedule/apply", json=_run_body())
    assert resp.json()["data"]["plan_version"] == 2
    with factory() as session:
        assert current_plan_version(session) == 2


def test_api_schedule_never_writes_order_due_date(api_client):
    client, factory = api_client
    with factory() as session:
        before = get_order_due_date(session, "SO-002")
    client.post("/api/schedule/run", json=_run_body())
    with factory() as session:
        after = get_order_due_date(session, "SO-002")
    assert before == after == date(2026, 10, 7)


def test_api_user_patch_due_then_run_has_e2(api_client):
    client, _ = api_client
    client.patch("/api/orders/SO-002", json={"due_date": "2026-09-23"})
    resp = client.post("/api/schedule/run", json=_run_body())
    conflicts = resp.json()["data"]["result"]["conflicts"]
    assert any(c["code"] == "E2" for c in conflicts)
    due = client.get("/api/orders/SO-002").json()["data"]["due_date"]
    assert due == "2026-09-23"


def test_api_plan_get_after_run(api_client):
    client, _ = api_client
    client.post("/api/schedule/run", json=_run_body())
    resp = client.get("/api/plan")
    assert resp.json()["data"]["plan_version"] == 1
    assert resp.json()["data"]["result"]["tasks"]
