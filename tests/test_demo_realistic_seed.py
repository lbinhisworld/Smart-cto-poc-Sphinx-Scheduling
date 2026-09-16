"""拟真演示种子：漏斗分布、样品超期、待办素材。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)


def test_funnel_has_realistic_stage_counts():
    client.post("/api/demo/ensure-crm-seed")
    r = client.get("/api/crm/reports/funnel", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] >= 20
    assert data["counts"]["线索"] >= 4
    assert data["counts"]["成交"] >= 3
    assert all(data["counts"][st] > 0 for st in data["stages"])


def test_sample_weekly_shows_overdue():
    client.post("/api/demo/ensure-crm-seed")
    r = client.get("/api/crm/reports/sample-weekly", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["active_count"] >= 6
    assert data["overdue_count"] >= 1
