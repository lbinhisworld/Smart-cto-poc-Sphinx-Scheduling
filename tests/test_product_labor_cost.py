"""C 链路：按成品品项汇总计划人工成本。"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.hr_seed import ensure_hr_seed
from db.product_labor_cost import planned_labor_cost_by_product
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from tests.conftest import ROOT, TODAY


@pytest.fixture
def scheduled_client(tmp_path):
    db_path = tmp_path / "labor_prod.db"
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
        client.post(
            "/api/schedule/run",
            json={"order_nos": ["SO-001", "SO-002"], "today": TODAY.isoformat(), "reserved_ratio": 0},
        )
        yield client


HDR = {"X-Demo-Role": "GM"}


def test_planned_labor_by_product_after_schedule(scheduled_client):
    client = scheduled_client
    resp = client.get("/api/hr/labor-cost/by-product", headers=HDR)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan_version"] > 0
    assert data["totals"]["hours_man"] > 0
    codes = {p["item_code"] for p in data["products"]}
    assert "P1" in codes or "P2" in codes
