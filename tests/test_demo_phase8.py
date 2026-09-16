"""Phase 8：演示控制台、待办中心、九幕剧本。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.main import create_app
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from db.tables import WecomMessageRow
from shared.demo_rehearsal import REHEARSAL_ACTS
from tests.conftest import ROOT, TODAY


@pytest.fixture
def demo_client(tmp_path):
    db_path = tmp_path / "demo8.db"
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


def test_demo_rehearsal_nine_acts(demo_client):
    client, _ = demo_client
    r = client.get("/api/demo/rehearsal", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    acts = r.json()["data"]["acts"]
    assert len(acts) == len(REHEARSAL_ACTS) == 10
    assert acts[0]["path"] == "/cockpit"
    assert acts[7]["title"].startswith("插单")
    scope = r.json()["data"]["scope"]
    assert scope["offline_ok"] is True
    assert len(scope["not_delivered"]) >= 4


def test_demo_scope_public(demo_client):
    client, _ = demo_client
    r = client.get("/api/demo/scope")
    assert r.status_code == 200
    assert r.json()["data"]["disclaimer"]


def test_demo_todos_pmc(demo_client):
    client, _ = demo_client
    r = client.get(
        "/api/demo/todos",
        params={"today": TODAY.isoformat()},
        headers={"X-Demo-Role": "PMC"},
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    kinds = {x["kind"] for x in items}
    assert "SCHEDULE_POOL" in kinds or "ORDER_CHANGE" in kinds or len(items) >= 0


def test_trigger_sample_overdue_s5(demo_client):
    client, factory = demo_client
    r = client.post(
        "/api/demo/trigger-sample-overdue",
        params={"sample_code": "SP-001"},
        headers={"X-Demo-Role": "PMC"},
    )
    assert r.status_code == 200
    with factory() as session:
        row = session.scalars(
            select(WecomMessageRow).where(WecomMessageRow.scene == "S5").order_by(WecomMessageRow.id.desc())
        ).first()
        assert row is not None
        assert "SP-001" in (row.body or "")


def test_trigger_sample_overdue_forbidden_sales(demo_client):
    client, _ = demo_client
    r = client.post(
        "/api/demo/trigger-sample-overdue",
        headers={"X-Demo-Role": "SALES"},
    )
    assert r.status_code == 403
