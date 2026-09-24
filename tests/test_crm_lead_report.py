from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)


def test_lead_report_api():
    r = client.get("/api/crm/leads/report?today=2026-09-15", headers={"X-Demo-Role": "SALES_MGR"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert "summary" in data
    assert data["summary"]["线索总数"] >= 1


def test_payment_plans_api():
    r = client.get("/api/crm/payment-plans?today=2026-09-15", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)
