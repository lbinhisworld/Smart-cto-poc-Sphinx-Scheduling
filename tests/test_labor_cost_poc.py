"""M1b 人工成本 POC。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from api.app_factory import app
from shared.labor_math import labor_cost, variance_pct

client = TestClient(app)


def _ensure_plan():
    client.post("/api/demo/ensure-crm-seed")
    pool = client.post(
        "/api/orders/scheduling-pool",
        headers={"X-Demo-Role": "PMC"},
        json={"action": "add", "order_nos": ["SO-001", "SO-002"]},
    )
    if pool.status_code == 200:
        client.post(
            "/api/orders/publish",
            headers={"X-Demo-Role": "PMC"},
            json={"today": "2026-09-15", "force_red": True},
        )


def test_labor_math():
    assert labor_cost(Decimal("10"), Decimal("48")) == Decimal("480.00")
    assert variance_pct(Decimal("100"), Decimal("110")) == Decimal("10.0")


def test_planned_and_summary_after_publish():
    _ensure_plan()
    r = client.get(
        "/api/labor/planned?date_from=2026-09-01&date_to=2026-09-30",
        headers={"X-Demo-Role": "PMC"},
    )
    assert r.status_code == 200
    cells = r.json()["data"]
    assert isinstance(cells, list)
    if cells:
        assert "hours_man_planned" in cells[0]

    summary = client.get(
        "/api/hr/labor-cost/summary?date_from=2026-09-01&date_to=2026-09-30",
        headers={"X-Demo-Role": "HR"},
    )
    assert summary.status_code == 200
    assert "rows" in summary.json()["data"]


def test_team_leader_confirm_and_forbidden_other_group():
    _ensure_plan()
    grid = client.get(
        "/api/labor/time-reports/grid?work_date=2026-09-15",
        headers={"X-Demo-Role": "TEAM_LEADER"},
    )
    assert grid.status_code == 200
    rows = grid.json()["data"]
    manual = next(x for x in rows if x["group_code"] == "MANUAL" and x["schedule_dept"] == "FINISHED_DEPT")
    assert manual["hours_man_planned"] >= 0

    save = client.post(
        "/api/labor/time-reports",
        headers={"X-Demo-Role": "TEAM_LEADER"},
        json={
            "work_date": "2026-09-15",
            "schedule_dept": "FINISHED_DEPT",
            "group_code": "MANUAL",
            "hours_man_actual": 12.5,
        },
    )
    assert save.status_code == 200
    rid = save.json()["data"]["id"]
    conf = client.post(
        f"/api/labor/time-reports/{rid}/confirm",
        headers={"X-Demo-Role": "TEAM_LEADER"},
    )
    assert conf.status_code == 200
    body = conf.json()["data"]
    assert body["status"] == "CONFIRMED"
    assert body["cost_actual"] is not None

    bad = client.post(
        "/api/labor/time-reports",
        headers={"X-Demo-Role": "TEAM_LEADER"},
        json={
            "work_date": "2026-09-15",
            "schedule_dept": "FINISHED_DEPT",
            "group_code": "MOLD",
            "hours_man_actual": 8,
        },
    )
    assert bad.status_code == 403


def test_time_report_rejects_over_attendance_and_missing_punch():
    _ensure_plan()
    grid = client.get(
        "/api/labor/time-reports/grid?work_date=2026-09-15",
        headers={"X-Demo-Role": "PMC"},
    )
    assert grid.status_code == 200
    rows = grid.json()["data"]
    manual = next(x for x in rows if x["group_code"] == "MANUAL" and x["schedule_dept"] == "FINISHED_DEPT")
    cap = manual.get("hours_cap")
    assert cap is not None
    assert cap > 0

    over = client.post(
        "/api/labor/time-reports",
        headers={"X-Demo-Role": "PMC"},
        json={
            "work_date": "2026-09-15",
            "schedule_dept": "FINISHED_DEPT",
            "group_code": "MANUAL",
            "hours_man_actual": float(cap) + 1,
        },
    )
    assert over.status_code == 400

    ok = client.post(
        "/api/labor/time-reports",
        headers={"X-Demo-Role": "PMC"},
        json={
            "work_date": "2026-09-15",
            "schedule_dept": "FINISHED_DEPT",
            "group_code": "MANUAL",
            "hours_man_actual": float(cap),
        },
    )
    assert ok.status_code == 200

    pouring = next(x for x in rows if x["group_code"] == "POURING" and x["schedule_dept"] == "FINISHED_DEPT")
    assert pouring.get("hours_cap") is None
    missing = client.post(
        "/api/labor/time-reports",
        headers={"X-Demo-Role": "PMC"},
        json={
            "work_date": "2026-09-15",
            "schedule_dept": "FINISHED_DEPT",
            "group_code": "POURING",
            "hours_man_actual": 8,
        },
    )
    assert missing.status_code == 400


def test_timeline_lists_only_planned_groups_and_splits_open_done():
    _ensure_plan()
    r = client.get(
        "/api/labor/time-reports/timeline?today=2026-09-15",
        headers={"X-Demo-Role": "PMC"},
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["plan_version"] >= 1
    assert data["today"] == "2026-09-15"
    nodes = data["open"] + data["done"]
    assert nodes, "发布后应有计划日期"
    for node in nodes:
        assert node["rows"]
        assert node["bucket"] in ("overdue", "today", "upcoming")
        for row in node["rows"]:
            assert row["hours_man_planned"] > 0
            assert row["work_date"] == node["work_date"]
    for node in data["open"]:
        assert any(row["status"] != "CONFIRMED" for row in node["rows"])
    for node in data["done"]:
        assert all(row["status"] == "CONFIRMED" for row in node["rows"])

    tl = client.get(
        "/api/labor/time-reports/timeline?today=2026-09-15",
        headers={"X-Demo-Role": "TEAM_LEADER"},
    )
    assert tl.status_code == 200
    for node in tl.json()["data"]["open"] + tl.json()["data"]["done"]:
        for row in node["rows"]:
            assert row["schedule_dept"] == "FINISHED_DEPT"
            assert row["group_code"] == "MANUAL"
