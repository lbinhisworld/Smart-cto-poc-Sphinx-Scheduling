"""封印库只读 API：可查树/卡/询问，不能写。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.session import init_db, make_engine, session_factory


@pytest.fixture
def api_client(tmp_path):
    engine = make_engine(tmp_path / "kb_api.db")
    init_db(engine)
    app = create_app(session_factory(engine))
    with TestClient(app) as client:
        yield client


def test_tree_has_order_slot(api_client) -> None:
    r = api_client.get("/api/kb/tree")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    ids = _collect_ids(body["data"]["roots"])
    assert "D.order" in ids
    assert "D.order.due_date" in ids
    assert "D.sph" in ids
    assert "D.trace" not in ids
    runtime = _collect_ids(body["data"].get("runtime") or [])
    assert "D.trace" in runtime
    assert "D.schedule_io" in runtime


def test_ops_stream_tree(api_client) -> None:
    r = api_client.get("/api/kb/ops")
    assert r.status_code == 200
    data = r.json()["data"]
    ids = _collect_ids(data["roots"])
    assert "F.l1.due_is_shared_reality" in ids
    assert "F.l3.vsm.order_to_delivery" in ids
    assert "F.l3.stg.demand" in ids
    assert "F.l3.due_change_via_approval" in ids
    assert "F.l3.menu_portal" not in ids
    due = next(node for node in data["roots"] if node["id"] == "F.l1.due_is_shared_reality")
    assert "F.l2.sales_owns_promise" in {cap["id"] for cap in due["capabilities"]}
    assert "F.l2.sales_owns_promise" not in _collect_ids(due["children"])
    loose_ids = {node["id"] for node in data["unattached"]}
    assert "F.l2.sales_owns_promise" not in loose_ids
    assert all(not item.startswith("F.l2.role_") for item in loose_ids)


def test_capability_card_fields(api_client) -> None:
    r = api_client.get("/api/kb/card/F.l2.sales_owns_promise")
    assert r.status_code == 200
    card = r.json()["data"]
    assert card["层"] == "权责"
    assert card["角色"] == "销售"
    assert "F.l1.due_is_shared_reality" in card["撑住谁"]


def test_card_is_readonly_view(api_client) -> None:
    r = api_client.get("/api/kb/card/D.order.due_date")
    assert r.status_code == 200
    card = r.json()["data"]
    assert card["编号"] == "D.order.due_date"
    assert card["属于"] == "D.order"
    assert "定义" in card


def test_ask_e2(api_client) -> None:
    r = api_client.post(
        "/api/kb/ask",
        json={"question": "E2 了能不能改订单交期", "role": "销售"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["verdict"] == "成立"
    assert data["mode"] == "原理"
    assert "F.l1.due_is_shared_reality" in data["chain"]
    assert "不会改订单日期" in data["text"]


def test_no_write_routes(api_client) -> None:
    assert api_client.put("/api/kb/card/D.order.due_date", json={}).status_code in {404, 405}
    assert api_client.patch("/api/kb/card/D.order.due_date", json={}).status_code in {404, 405}
    assert api_client.delete("/api/kb/card/D.order.due_date").status_code in {404, 405}


def test_pending_and_probe_readonly(api_client) -> None:
    pending = api_client.get("/api/kb/pending", params={"theme": "履约四环节"})
    assert pending.status_code == 200
    body = pending.json()["data"]
    assert body["readonly"] is True
    ids = {item["shallow_id"] for item in body["items"]}
    assert ids == {
        "F.l3.stg.demand",
        "F.l3.stg.schedule",
        "F.l3.stg.make",
        "F.l3.stg.fulfill",
    }
    probe = api_client.get("/api/kb/probe", params={"theme": "履约四环节"})
    anchors = {item["anchor"] for item in probe.json()["data"]["items"]}
    assert "F.l1.mto_no_fg_stock" in anchors
    assert "D.insert" not in anchors
    themes = api_client.get("/api/kb/themes").json()["data"]
    assert themes["default"] == "履约四环节"
    assert themes["readonly"] is True


def test_nod_requires_role(api_client) -> None:
    r = api_client.post(
        "/api/kb/nod",
        json={"叶子": "F.l3.stg.schedule", "主题": "履约四环节", "结果": "认"},
    )
    assert r.status_code == 403


def test_seal_requires_nod_ren(api_client) -> None:
    r = api_client.post(
        "/api/kb/seal",
        json={"叶子": "F.l3.stg.schedule", "主题": "履约四环节"},
        headers={"X-Demo-Role": "GM"},
    )
    assert r.status_code == 403


def _collect_ids(nodes: list[dict]) -> set[str]:
    found: set[str] = set()
    for node in nodes:
        found.add(node["id"])
        found |= _collect_ids(node.get("children") or [])
    return found
