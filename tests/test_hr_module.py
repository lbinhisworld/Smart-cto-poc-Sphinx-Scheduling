"""M1 人事：花名册与考勤明细。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)
HDR = {"X-Demo-Role": "HR"}


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
    assert by_no["E1002"]["contract_status"] == "EXPIRED"
    assert by_no["E2001"]["contract_status"] == "OK"

    detail = client.get("/api/hr/employees/E1002?today=2026-09-15", headers=HDR)
    assert detail.status_code == 200
    assert detail.json()["data"]["contract_status"] == "EXPIRED"

    todos = client.get("/api/demo/todos?today=2026-09-15", headers=HDR).json()["data"]["items"]
    contract_todos = [t for t in todos if t["kind"] == "HR_CONTRACT"]
    assert contract_todos
    titles = " ".join(t["title"] + t.get("detail", "") for t in contract_todos)
    assert "E1002" in titles
    assert "E1001" in titles
