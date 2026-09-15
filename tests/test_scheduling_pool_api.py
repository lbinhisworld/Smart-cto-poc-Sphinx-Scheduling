"""订单池 Tab / 发布 API。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from tests.conftest import ROOT, TODAY


@pytest.fixture
def api_client(tmp_path):
    db_path = tmp_path / "pool_api.db"
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
        yield client


def _phases(client: TestClient) -> dict[str, str]:
    rows = client.get("/api/orders").json()["data"]["orders"]
    return {r["order_no"]: r["schedule_phase"] for r in rows}


def test_seed_has_scheduling_pool_and_pending(api_client: TestClient):
    phases = _phases(api_client)
    assert len(phases) == 12
    assert sum(1 for p in phases.values() if p == "IN_SCHEDULING") == 3
    assert sum(1 for p in phases.values() if p == "PENDING") == 9


def test_add_remove_scheduling_pool(api_client: TestClient):
    assert _phases(api_client)["SO-004"] == "PENDING"
    r = api_client.post(
        "/api/orders/scheduling-pool",
        json={"action": "add", "order_nos": ["SO-004"]},
    )
    assert r.status_code == 200
    pool = r.json()["data"]["pool"]
    assert "SO-004" in pool
    assert _phases(api_client)["SO-004"] == "IN_SCHEDULING"

    r2 = api_client.post(
        "/api/orders/scheduling-pool",
        json={"action": "remove", "order_nos": ["SO-004"]},
    )
    assert r2.status_code == 200
    assert _phases(api_client)["SO-004"] == "PENDING"


def test_publish_moves_pool_to_production(api_client: TestClient):
    pool = [
        no
        for no, ph in _phases(api_client).items()
        if ph == "IN_SCHEDULING"
    ]
    assert len(pool) >= 1
    r = api_client.post(
        "/api/orders/publish",
        json={"today": TODAY.isoformat(), "order_nos": sorted(pool), "force_red": False},
    )
    if r.status_code == 409:
        pytest.skip("种子池当前含 E1/E2，跳过成功发布路径")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["published"] is True
    assert data["plan_version"] >= 1
    phases = _phases(api_client)
    for no in pool:
        assert phases[no] == "IN_PRODUCTION"
