"""MIS 新建订单 API。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)
HDR = {"X-Demo-Role": "SALES", "Content-Type": "application/json"}


def test_create_mis_order_multi_line():
    client.post("/api/demo/ensure-crm-seed")
    body = {
        "customer_code": "C-001",
        "contract_no": "CT-202609-0001",
        "due_date": "2026-10-01",
        "sales_name": "陈雨桐",
        "lines": [
            {"item_code": "P1", "qty": 10, "unit": "BOX"},
            {"item_code": "P4", "qty": 5, "unit": "BOX"},
        ],
    }
    r = client.post("/api/mis/orders", headers=HDR, json=body)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    order_no = data["order_no"]
    assert data["schedule_phase"] == "PENDING"
    assert data["line_count"] == 2

    rows = client.get("/api/mis/orders?view=pending", headers={"X-Demo-Role": "GM"}).json()["data"]["rows"]
    assert any(x["order_no"] == order_no for x in rows)
