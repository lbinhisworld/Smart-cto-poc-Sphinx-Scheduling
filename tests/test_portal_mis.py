"""M0 门户与 MIS 订单列表（Phase 0–3）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)


def test_portal_roles():
    r = client.get("/api/portal/roles")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 11
    codes = {x["code"] for x in data}
    assert "PMC" in codes and "SALES" in codes and "TEAM_LEADER" in codes
    assert "RD" in codes and "SALES_ASSIST" in codes


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


def test_sales_menu_is_mobile_crm_not_visit_tool():
    r = client.get("/api/portal/menu", headers={"X-Demo-Role": "SALES"})
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    visit = next(x for x in items if x["key"] == "crm_visit")
    assert visit["label"] == "销售移动端"
    assert visit["path"] == "/crm/visit"
    progress = next(x for x in items if x["key"] == "crm_progress")
    assert progress["label"] == "签约产品生产进度"
    assert next(x for x in items if x["key"] == "crm_customers")["label"] == "我的客户"
    assert all(x["key"] != "settings" for x in items)


def test_gm_menu_has_system_settings():
    r = client.get("/api/portal/menu", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    settings = next(x for x in items if x["key"] == "settings")
    assert settings["label"] == "系统配置"
    assert settings["path"] == "/settings"
    visit = next(x for x in items if x["key"] == "crm_visit")
    assert visit["label"] == "销售移动端"


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
