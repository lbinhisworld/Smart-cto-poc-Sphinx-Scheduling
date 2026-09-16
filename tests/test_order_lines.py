"""订单多行明细（MIS）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)
HDR = {"X-Demo-Role": "GM"}


def test_mis_order_has_multi_lines():
    client.post("/api/demo/ensure-crm-seed")
    r = client.get("/api/mis/orders/SO-002/breakdown", headers=HDR)
    assert r.status_code == 200
    lines = r.json()["data"]["lines"]
    assert len(lines) >= 2
    assert lines[0]["unit"] == "BOX"


def test_mis_list_lines_summary():
    client.post("/api/demo/ensure-crm-seed")
    rows = client.get("/api/mis/orders?view=all", headers=HDR).json()["data"]["rows"]
    so2 = next(x for x in rows if x["order_no"] == "SO-002")
    assert so2["line_count"] >= 2
    assert "P2" in so2["lines_summary"]
