"""电脑端外勤 · 写入跟进。"""

from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from api.app_factory import app
from db.session import make_engine, session_factory
from db.tables import CrmFieldVisitRow

client = TestClient(app)
SALES = {"X-Demo-Role": "SALES"}


def test_parse_and_confirm_visit_flow():
    created = client.post(
        "/api/crm/checkin",
        headers={**SALES, "Content-Type": "application/json"},
        json={"title": "pytest外勤", "customer_code": "C-001", "situation_note": "现场沟通顺利"},
    )
    assert created.status_code == 200
    code = created.json()["data"]["code"]
    parsed = client.post(
        f"/api/crm/checkin/{code}/parse",
        headers={**SALES, "Content-Type": "application/json"},
        json={"raw_text": "客户有采购意向"},
    )
    assert parsed.status_code == 200
    assert "AI整理" in parsed.json()["data"]["parsed"]
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
        headers={**SALES, "Content-Type": "application/json"},
        json={},
    )
    assert confirm.status_code == 200, confirm.text
