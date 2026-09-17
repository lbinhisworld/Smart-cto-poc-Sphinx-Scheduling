"""客户 360 API。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)
HDR = {"X-Demo-Role": "GM"}


def test_customer_360_has_histories():
    client.post("/api/demo/ensure-crm-seed")
    r = client.get("/api/crm/customers/C-001", headers=HDR)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["customer"]["name"]
    assert isinstance(data["samples"], list)
    assert isinstance(data["opportunities"], list)
    assert isinstance(data["orders"], list)
    assert isinstance(data.get("complaints"), list)


def test_customer_360_complaints_linked_to_c001():
    client.post("/api/demo/ensure-crm-seed")
    r = client.get("/api/crm/customers/C-001", headers=HDR)
    complaints = r.json()["data"].get("complaints") or []
    assert any(c.get("customer_code") == "C-001" for c in complaints)


def test_opportunity_detail():
    client.post("/api/demo/ensure-crm-seed")
    opps = client.get("/api/crm/opportunities", headers=HDR).json()["data"]
    assert opps
    assert opps[0].get("sales_name")
    linked = next(o for o in opps if o.get("name") == "新品打样跟进")
    assert linked is not None
    r = client.get(f"/api/crm/opportunities/{linked['id']}", headers=HDR)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["customer"]["code"] == "C-003"
    assert body["sample"]["code"] == "SP-002"
    assert len(body["sample"]["steps"]) >= 2
