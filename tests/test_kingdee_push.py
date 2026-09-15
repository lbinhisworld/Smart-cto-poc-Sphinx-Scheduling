"""Phase 4：金蝶 Push 模拟 + 齐套回写。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)
HDR = {"X-Demo-Role": "PMC"}


def test_kingdee_simulate_push_creates_order_and_log():
    r = client.post(
        "/api/kingdee/simulate-push",
        headers=HDR,
        json={"template_key": "demo_p4"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    order_no = body["data"]["order_no"]
    assert order_no.startswith("SO-KD-")

    r2 = client.get(f"/api/mis/orders/{order_no}/breakdown", headers=HDR)
    assert r2.status_code == 200
    bd = r2.json()["data"]
    assert bd["order"]["order_source"] == "KINGDEE"
    assert bd["kitting"]["kitting_rate_pct"] is not None

    logs = client.get("/api/kingdee/logs", headers=HDR).json()["data"]
    assert any(x["doc_no"] == order_no and x["status"] == "SUCCESS" for x in logs)


def test_mis_add_scheduling_pool():
    push = client.post(
        "/api/kingdee/simulate-push",
        headers=HDR,
        json={"template_key": "demo_p2"},
    ).json()
    order_no = push["data"]["order_no"]
    r = client.post(
        "/api/mis/orders/scheduling-pool",
        headers=HDR,
        json={"order_nos": [order_no]},
    )
    assert r.status_code == 200
    assert order_no in r.json()["data"]["pool"]
