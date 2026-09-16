"""M0 门户与 MIS 订单列表（Phase 0–3）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)


def test_portal_roles():
    r = client.get("/api/portal/roles")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 8
    codes = {x["code"] for x in data}
    assert "PMC" in codes and "SALES" in codes and "TEAM_LEADER" in codes


def test_portal_menu_requires_role():
    r = client.get("/api/portal/menu")
    assert r.status_code == 401


def test_portal_menu_pmc():
    r = client.get("/api/portal/menu", headers={"X-Demo-Role": "PMC"})
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    paths = {x["path"] for x in items}
    assert "/schedule" in paths
    assert "/orders" in paths


def test_mis_orders_sales_hides_amount():
    r = client.get("/api/mis/orders", headers={"X-Demo-Role": "SALES"})
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["field_perm"]["amount_hidden"] is True
    if body["rows"]:
        assert body["rows"][0]["amount"] is None


def test_crm_seed_opportunities():
    r = client.post("/api/demo/ensure-crm-seed")
    assert r.status_code == 200
    from sqlalchemy import func, select

    from db.session import make_engine, session_factory
    from db.tables import CrmOpportunityRow

    engine = make_engine(__import__("pathlib").Path("data/scheduling.db"))
    factory = session_factory(engine)
    session = factory()
    try:
        n = session.scalar(select(func.count()).select_from(CrmOpportunityRow)) or 0
        assert n >= 6
    finally:
        session.close()
