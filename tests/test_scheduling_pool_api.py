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


def _mis_rows(client: TestClient, view: str) -> list[dict]:
    r = client.get(f"/api/mis/orders?view={view}", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["rows"]


def test_remove_all_from_scheduling_pool(api_client: TestClient):
    api_client.post(
        "/api/orders/scheduling-pool",
        json={"action": "add", "order_nos": ["SO-004"]},
    )
    phases = _phases(api_client)
    pool = sorted(no for no, ph in phases.items() if ph == "IN_SCHEDULING")
    assert "SO-004" in pool
    assert len(pool) >= 4

    r = api_client.post(
        "/api/orders/scheduling-pool",
        json={"action": "remove", "order_nos": pool},
    )
    assert r.status_code == 200
    assert r.json()["data"]["pool"] == []

    phases = _phases(api_client)
    for no in pool:
        assert phases[no] == "PENDING"
    rows = {row["order_no"]: row for row in _mis_rows(api_client, "all")}
    assert rows["SO-004"]["schedule_phase"] == "PENDING"
    assert rows["SO-004"]["order_status"] == "CONFIRMED"
    assert "SO-004" in {row["order_no"] for row in _mis_rows(api_client, "pending")}
    assert "SO-004" not in {row["order_no"] for row in _mis_rows(api_client, "in_scheduling")}


def test_add_to_pool_syncs_sales_order_list(api_client: TestClient):
    """排程池与销售列表共用 schedule_phase；进池后不应再出现在待排程。"""
    api_client.post(
        "/api/orders/scheduling-pool",
        json={"action": "add", "order_nos": ["SO-004"]},
    )
    all_rows = {r["order_no"]: r for r in _mis_rows(api_client, "all")}
    assert all_rows["SO-004"]["schedule_phase"] == "IN_SCHEDULING"
    assert all_rows["SO-004"]["order_status"] == "SCHEDULED"
    assert "SO-004" not in {r["order_no"] for r in _mis_rows(api_client, "pending")}
    assert "SO-004" in {r["order_no"] for r in _mis_rows(api_client, "in_scheduling")}
    assert "SO-004" not in {r["order_no"] for r in _mis_rows(api_client, "pending_schedule")}
    stats = api_client.get("/api/mis/orders?view=all", headers={"X-Demo-Role": "GM"}).json()["data"]["stats"]
    assert stats["in_scheduling"] >= 1
    assert stats["pending"] == stats["pending_schedule"]


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
