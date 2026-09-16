"""M1 人事：花名册与考勤明细。"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from api.app_factory import app
from db.hr_queries import contract_status_for, days_until_renewal, renewal_status_label

client = TestClient(app)
HDR = {"X-Demo-Role": "HR"}
ANCHOR = date(2026, 9, 15)


def test_renewal_status_and_countdown_helpers():
    assert contract_status_for(date(2026, 10, 10), today=ANCHOR, remind_days=30) == "DUE_SOON"
    assert days_until_renewal(date(2026, 10, 10), today=ANCHOR) == 25
    assert renewal_status_label("DUE_SOON") == "一个月内续签"

    assert contract_status_for(date(2026, 9, 1), today=ANCHOR, remind_days=30) == "EXPIRED"
    assert days_until_renewal(date(2026, 9, 1), today=ANCHOR) == -14
    assert renewal_status_label("EXPIRED") == "续签过期"

    assert contract_status_for(date(2027, 12, 31), today=ANCHOR, remind_days=30) == "OK"
    assert days_until_renewal(date(2027, 12, 31), today=ANCHOR) == 472
    assert renewal_status_label("OK") == "正常"

    assert contract_status_for(None, today=ANCHOR, remind_days=30) == "OK"
    assert days_until_renewal(None, today=ANCHOR) is None
    assert contract_status_for(ANCHOR, today=ANCHOR, remind_days=30) == "DUE_SOON"
    assert days_until_renewal(ANCHOR, today=ANCHOR) == 0
    assert contract_status_for(date(2026, 10, 15), today=ANCHOR, remind_days=30) == "DUE_SOON"
    assert contract_status_for(date(2026, 10, 16), today=ANCHOR, remind_days=30) == "OK"


def test_hr_employees_and_punches():
    r = client.get("/api/hr/employees", headers=HDR)
    assert r.status_code == 200
    employees = r.json()["data"]
    assert len(employees) >= 10
    assert employees[0]["name"]
    assert employees[0]["department"]

    detail = client.get(f"/api/hr/employees/{employees[0]['emp_no']}", headers=HDR)
    assert detail.status_code == 200
    assert detail.json()["data"]["position"]

    punches = client.get("/api/hr/attendance/punches?work_date=2026-09-15", headers=HDR)
    assert punches.status_code == 200
    rows = punches.json()["data"]
    assert len(rows) >= 5
    assert rows[0]["device_name"]
    assert rows[0]["synced_at"]
    assert rows[0]["punch_type"] in ("上班", "下班")


def test_hr_contract_status_and_todos():
    r = client.get("/api/hr/employees?today=2026-09-15", headers=HDR)
    assert r.status_code == 200
    by_no = {e["emp_no"]: e for e in r.json()["data"]}
    assert by_no["E1001"]["contract_status"] == "DUE_SOON"
    assert by_no["E1001"]["contract_end"] == "2026-10-10"
    assert by_no["E1001"]["days_until_renewal"] == 25
    assert by_no["E1001"]["renewal_status_label"] == "一个月内续签"
    assert by_no["E1002"]["contract_status"] == "EXPIRED"
    assert by_no["E1002"]["days_until_renewal"] == -14
    assert by_no["E1002"]["renewal_status_label"] == "续签过期"
    assert by_no["E2001"]["contract_status"] == "OK"
    assert by_no["E2001"]["days_until_renewal"] == 472
    assert by_no["E2001"]["renewal_status_label"] == "正常"

    counts = {k: 0 for k in ("OK", "DUE_SOON", "EXPIRED")}
    for e in by_no.values():
        counts[e["contract_status"]] += 1
    assert counts["DUE_SOON"] >= 1
    assert counts["EXPIRED"] >= 1
    assert counts["OK"] >= 1

    detail = client.get("/api/hr/employees/E1002?today=2026-09-15", headers=HDR)
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["contract_status"] == "EXPIRED"
    assert body["days_until_renewal"] == -14
    assert body["renewal_status_label"] == "续签过期"

    soon = client.get("/api/hr/employees/E1001?today=2026-09-15", headers=HDR)
    assert soon.status_code == 200
    soon_body = soon.json()["data"]
    assert soon_body["days_until_renewal"] == 25
    assert soon_body["renewal_status_label"] == "一个月内续签"

    todos = client.get("/api/demo/todos?today=2026-09-15", headers=HDR).json()["data"]["items"]
    contract_todos = [t for t in todos if t["kind"] == "HR_CONTRACT"]
    assert contract_todos
    titles = " ".join(t["title"] + t.get("detail", "") for t in contract_todos)
    assert "E1002" in titles
    assert "E1001" in titles
    assert "续签过期" in titles
    assert "一个月内续签" in titles
    expired_todo = next(t for t in contract_todos if "E1002" in t["title"])
    assert "renewal=EXPIRED" in expired_todo["path"]
