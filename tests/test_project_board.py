"""大客户专项进度大盘：四列完成日、格内时间线、登记日期不改交期。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sqlalchemy import select

from api.app_factory import app
from db.project_board import ensure_project_board
from db.session import make_engine, session_factory
from db.tables import SoOrderRow

client = TestClient(app)
GM = {"X-Demo-Role": "GM"}


def _reset() -> None:
    factory = session_factory(make_engine())
    session = factory()
    try:
        ensure_project_board(session, force=True)
        session.commit()
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _fresh_projects():
    _reset()
    yield
    _reset()


def _board() -> dict:
    r = client.get("/api/modules/project/board", headers=GM)
    assert r.status_code == 200
    return r.json()["data"]


def _due_map() -> dict[str, str]:
    session = session_factory(make_engine())()
    try:
        rows = session.scalars(select(SoOrderRow)).all()
        return {r.order_no: r.due_date.isoformat() for r in rows}
    finally:
        session.close()


def test_board_seed_three_large_customer_projects():
    data = _board()
    assert [s["name"] for s in data["stages"]] == ["立项", "采购", "试机", "投产"]
    assert data["active_projects"] == 2
    assert data["launched_projects"] == 1
    by_code = {p["code"]: p for p in data["projects"]}

    done = by_code["PJ-001"]
    assert done["customer_name"] == "好利来食品"
    assert done["status"] == "已投产"
    assert done["order_no"] == "SO-005"
    assert done["cells"]["INIT"] == {"done": True, "completed_on": "2026-06-18"}
    assert done["cells"]["PROCURE"]["completed_on"] == "2026-08-01"
    assert done["cells"]["TRIAL"]["completed_on"] == "2026-08-28"
    assert done["cells"]["RAMP"]["completed_on"] == "2026-09-12"

    trial = by_code["PJ-002"]
    assert trial["status"] == "进行中"
    assert trial["cells"]["INIT"]["done"] is True
    assert trial["cells"]["PROCURE"]["done"] is True
    assert trial["cells"]["TRIAL"] == {"done": False, "completed_on": None}
    assert trial["cells"]["RAMP"]["done"] is False

    early = by_code["PJ-003"]
    assert early["cells"]["INIT"]["done"] is True
    assert early["cells"]["PROCURE"]["done"] is False
    assert early["cells"]["TRIAL"]["done"] is False


def test_cell_opens_stage_timeline():
    ramp = client.get("/api/modules/project/PJ-001/stages/RAMP", headers=GM)
    assert ramp.status_code == 200
    body = ramp.json()["data"]
    assert body["done"] is True
    assert body["handoff"] == "可交排程"
    assert body["order_no"] == "SO-005"
    assert [s["name"] for s in body["steps"]] == ["试产通过", "转正式生产", "交排程"]
    assert all(s["event_date"] for s in body["steps"])

    trial = client.get("/api/modules/project/PJ-002/stages/TRIAL", headers=GM).json()["data"]
    assert trial["done"] is False
    assert trial["steps"][0]["event_date"] == "2026-09-08"
    assert trial["steps"][1]["event_date"] is None
    assert trial["steps"][1]["name"] == "调试"
    assert trial["handoff"] is None


def test_later_stage_can_be_dated_before_previous_gate_is_green():
    detail = client.get("/api/modules/project/PJ-003/stages/TRIAL", headers=GM).json()["data"]
    assert detail["steps"][0]["name"] == "进场"
    assert detail["steps"][0]["event_date"] == "2026-09-05"
    board = _board()
    cells = next(p for p in board["projects"] if p["code"] == "PJ-003")["cells"]
    assert cells["PROCURE"]["done"] is False
    assert cells["TRIAL"]["done"] is False


def test_filling_last_step_turns_cell_green_without_rewriting_due_date():
    due_before = _due_map()
    first = client.post(
        "/api/modules/project/PJ-003/steps",
        headers=GM,
        json={"stage_code": "PROCURE", "step_no": 2, "event_date": "2026-09-10"},
    )
    assert first.status_code == 200
    assert first.json()["data"]["done"] is False

    second = client.post(
        "/api/modules/project/PJ-003/steps",
        headers=GM,
        json={"stage_code": "PROCURE", "step_no": 3, "event_date": "2026-09-20"},
    )
    assert second.status_code == 200
    body = second.json()["data"]
    assert body["done"] is True
    assert body["completed_on"] == "2026-09-20"

    cells = next(p for p in _board()["projects"] if p["code"] == "PJ-003")["cells"]
    assert cells["PROCURE"] == {"done": True, "completed_on": "2026-09-20"}
    assert _due_map() == due_before


def test_ramp_without_order_says_not_yet_handed_to_scheduling():
    for step_no, event_date in ((1, "2026-09-16"), (2, "2026-09-18"), (3, "2026-09-20")):
        r = client.post(
            "/api/modules/project/PJ-003/steps",
            headers=GM,
            json={"stage_code": "RAMP", "step_no": step_no, "event_date": event_date},
        )
        assert r.status_code == 200
    body = r.json()["data"]
    assert body["done"] is True
    assert body["completed_on"] == "2026-09-20"
    assert body["handoff"] == "尚未建生产订单"
    assert body["order_no"] is None


def test_summary_uses_board_counts():
    data = client.get("/api/modules/project/summary", headers=GM).json()["data"]
    assert data["active_projects"] == 2
    assert data["launched_projects"] == 1
    assert "risk_projects" not in data


def test_board_is_gm_only():
    assert client.get("/api/modules/project/board", headers={"X-Demo-Role": "SALES"}).status_code == 403
    assert (
        client.post(
            "/api/modules/project/PJ-003/steps",
            headers={"X-Demo-Role": "PMC"},
            json={"stage_code": "PROCURE", "step_no": 2, "event_date": "2026-09-10"},
        ).status_code
        == 403
    )


def test_bad_date_and_missing_project():
    missing = client.get("/api/modules/project/NOPE/stages/INIT", headers=GM)
    assert missing.status_code == 404
    bad = client.post(
        "/api/modules/project/PJ-003/steps",
        headers=GM,
        json={"stage_code": "PROCURE", "step_no": 2, "event_date": "09-10"},
    )
    assert bad.status_code == 400
