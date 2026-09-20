"""BOM / 工艺路线 API。"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from tests.conftest import ROOT, TODAY


@pytest.fixture
def api_client(tmp_path):
    db_path = tmp_path / "bom_api.db"
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


def test_bom_catalog_has_nine_orders_demo(api_client):
    r = api_client.get("/api/bom")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["catalog"]) == 5
    assert data["seed_version"]
    codes = {x["item_code"] for x in data["items"]}
    assert "P2" in codes and "S2" not in codes


def test_bom_design_p2_two_layer(api_client):
    r = api_client.get("/api/bom/P2")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["pattern"] == "TWO_LAYER"
    assert d["finished"]["group_code"] == "MOLD"
    assert d["semi"]["item_code"] == "S2"
    assert d["semi"]["group_code"] == "MOLD"
    assert d["edge"]["semi_board_per_box"] == 2.0
    assert d["edge"]["lead_time_days"] == 4
    note = d.get("routing_note") or ""
    assert "工作中心" in note
    assert "流向" in note
    assert "一部" in d["finished"]["group_label"]
    assert "二部" in d["semi"]["group_label"]


def test_bom_design_p1_single_layer(api_client):
    d = api_client.get("/api/bom/P1").json()["data"]
    assert d["pattern"] == "SINGLE_LAYER"
    assert d["semi"] is None


def test_bom_explode_p2_200_box_matches_engine(api_client):
    r = api_client.get(
        "/api/bom/explode",
        params={"item_code": "P2", "qty": 200, "unit": "BOX", "today": TODAY.isoformat()},
    )
    assert r.status_code == 200
    e = r.json()["data"]
    assert e["finished_plan_board"] == 1236
    assert e["semi"]["gross_board"] == 412
    assert e["semi"]["net_board"] == 282
    assert e["semi"]["generates_semi_wo"] is True


def test_bom_explode_p2_stock_cover(api_client):
    """与 BR-32 一致：库存足够时不生成半成品工单（净需求 0）。"""
    r2 = api_client.get(
        "/api/bom/explode",
        params={"item_code": "P2", "qty": 50, "unit": "BOX"},
    )
    e2 = r2.json()["data"]
    assert e2["semi"]["net_board"] == 0
    assert e2["semi"]["generates_semi_wo"] is False


def test_bom_design_p9_multi_semi(api_client):
    d = api_client.get("/api/bom/P9").json()["data"]
    assert d["pattern"] == "MULTI_BOM"
    assert len(d["components"]) == 4
    semi = [c for c in d["components"] if c["role"] == "SEMI"]
    assert {c["node"]["item_code"] for c in semi} == {"S2", "S5", "S6"}
    pkg = next(c for c in d["components"] if c["role"] == "PURCHASED")
    assert pkg["node"]["item_code"] == "PKG-P9"
    assert pkg["node"]["stock_board"] == 80


def test_bom_design_p2_includes_purchased_component(api_client):
    d = api_client.get("/api/bom/P2").json()["data"]
    codes = [c["node"]["item_code"] for c in d["components"]]
    assert codes == ["S2", "PKG-P2"]
    pkg = next(c for c in d["components"] if c["role"] == "PURCHASED")
    assert pkg["node"]["stock_board"] == 500


def test_bom_explode_p9_line_details(api_client):
    e = api_client.get(
        "/api/bom/explode",
        params={"item_code": "P9", "qty": 60, "unit": "BOX", "today": TODAY.isoformat()},
    ).json()["data"]
    assert e["computable"] is True
    assert len(e["line_details"]) == 4
    semi_lines = [ln for ln in e["line_details"] if ln["role"] == "SEMI"]
    assert len(semi_lines) == 3
    assert len(e["steps"]) == 2


def test_bom_not_found(api_client):
    assert api_client.get("/api/bom/NOPE").status_code == 404
