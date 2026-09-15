"""库存中心 API。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from tests.conftest import ROOT


@pytest.fixture
def api_client(tmp_path):
    db_path = tmp_path / "stock_test.db"
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


def test_stock_list_and_patch(api_client):
    client = api_client
    resp = client.get("/api/stock")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    codes = {i["item_code"] for i in items}
    assert "S2" in codes
    assert "PKG-P2" in codes
    patch = client.patch("/api/stock/S2", json={"qty_available": 100})
    assert patch.status_code == 200
    assert patch.json()["data"]["qty_available"] == 100
    assert patch.json()["data"]["source"] == "LOCAL"


def test_stock_sync_erp_mock(api_client):
    client = api_client
    client.patch("/api/stock/S2", json={"qty_available": 1})
    sync = client.post("/api/stock/sync-erp-mock?mode=merge")
    assert sync.status_code == 200
    s2 = next(i for i in client.get("/api/stock").json()["data"]["items"] if i["item_code"] == "S2")
    assert s2["qty_available"] == 130
    assert s2["source"] == "ERP_MOCK"
