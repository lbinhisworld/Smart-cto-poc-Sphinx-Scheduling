"""拜访签到升级 · 时间线 / stats 路由 / 规则归纳。"""

from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from api.app_factory import app
from db.session import make_engine, session_factory
from db.tables import CrmFieldVisitRow

client = TestClient(app)
SALES = {"X-Demo-Role": "SALES", "Content-Type": "application/json"}


def test_checkin_stats_not_shadowed_by_code_route():
    r = client.get("/api/crm/checkin/stats?today=2026-09-15", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "not_meeting" in data
    assert "by_tag" in data


def test_timeline_finalize_and_confirm_flow():
    created = client.post(
        "/api/crm/checkin?today=2026-09-15",
        headers=SALES,
        json={"title": "pytest时间线", "customer_code": "C-001", "situation_note": "见到采购决策人，有打样意向"},
    )
    assert created.status_code == 200
    code = created.json()["data"]["code"]
    assert created.json()["data"]["status"] == "进行中"
    assert created.json()["data"]["started_at"]

    log = client.post(
        f"/api/crm/checkin/{code}/logs?today=2026-09-15",
        headers=SALES,
        json={"body": "离店后补充：确认下周打样数量"},
    )
    assert log.status_code == 200
    assert len(log.json()["data"]["timeline"]) >= 2

    fin = client.post(
        f"/api/crm/checkin/{code}/finalize?today=2026-09-15",
        headers=SALES,
        json={"prefer_llm": False},
    )
    assert fin.status_code == 200
    assert fin.json()["data"]["meets_standard"] is True
    assert fin.json()["data"]["progress_tags"]

    engine = make_engine(Path("data/scheduling.db"))
    s = session_factory(engine)()
    try:
        row = s.get(CrmFieldVisitRow, code)
        row.check_in_at = datetime(2026, 9, 15, 10, 0, 0)
        row.started_at = row.check_in_at
        s.commit()
    finally:
        s.close()

    out = client.post(f"/api/crm/checkin/{code}/sign-out", headers=SALES)
    assert out.status_code == 200, out.text

    confirm = client.post(
        f"/api/crm/checkin/{code}/confirm-follow?today=2026-09-15",
        headers=SALES,
        json={},
    )
    assert confirm.status_code == 200, confirm.text
