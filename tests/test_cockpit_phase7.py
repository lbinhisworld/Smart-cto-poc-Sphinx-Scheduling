from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)


def test_cockpit_and_module_summaries():
    r = client.get("/api/cockpit/snapshot", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    assert r.json()["data"]["legacy_excel_sheets"] == 20
    for path in (
        "/api/modules/hr/summary",
        "/api/modules/production/summary",
        "/api/modules/finance/summary",
        "/api/modules/project/summary",
    ):
        assert client.get(path, headers={"X-Demo-Role": "GM"}).status_code == 200
