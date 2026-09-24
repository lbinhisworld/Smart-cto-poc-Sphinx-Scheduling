"""打样流程详情与子表。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete

from api.app_factory import app
from db.session import make_engine, session_factory
from db.tables import CrmSampleRow, CrmSampleStepRow

client = TestClient(app)
HDR = {"X-Demo-Role": "GM"}
CLOSE_CODE = "SP-W1-CLOSE"


def _reset_close_fixture() -> None:
    engine = make_engine(Path(__file__).resolve().parents[1] / "data" / "scheduling.db")
    session = session_factory(engine)()
    try:
        session.execute(delete(CrmSampleStepRow).where(CrmSampleStepRow.sample_code == CLOSE_CODE))
        row = session.get(CrmSampleRow, CLOSE_CODE)
        if row is None:
            session.add(
                CrmSampleRow(
                    code=CLOSE_CODE,
                    customer_code="C-001",
                    item_draft_name="Wave1 结案证据",
                    current_stage="寄样",
                    round_no=1,
                    owner_sales="陈雨桐",
                    due_date=date(2026, 9, 20),
                    is_old_product=False,
                    result=None,
                )
            )
        else:
            row.current_stage = "寄样"
            row.result = None
        session.commit()
    finally:
        session.close()


def test_sample_detail_has_steps_and_customer():
    client.post("/api/demo/ensure-crm-seed")
    r = client.get("/api/crm/samples/SP-001", headers=HDR)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["current_stage"] == "打样"
    assert data["customer"]["code"] == "C-001"
    assert data["customer"]["name"]
    assert data["owner_sales"] == "陈雨桐"
    assert len(data["steps"]) >= 2
    assert data["steps"][0]["event_date"]
    assert data["steps"][0]["product_desc"]
    assert data["steps"][0]["situation_desc"]


def test_sample_add_step_and_final_requires_evidence():
    client.post("/api/demo/ensure-crm-seed")
    _reset_close_fixture()
    mid = client.post(
        f"/api/crm/samples/{CLOSE_CODE}/steps",
        headers=HDR,
        json={
            "stage": "打样",
            "event_date": "2026-09-14",
            "product_desc": "Wave1 试模",
            "situation_desc": "第4轮试模",
            "is_final": False,
        },
    )
    assert mid.status_code == 200
    body = mid.json()["data"]
    assert body["current_stage"] == "打样"
    assert len(body["steps"]) == 1
    assert body["steps"][0]["round_no"] == 1
    assert "第1轮" in body["steps"][0]["product_desc"]

    rework = client.post(
        f"/api/crm/samples/{CLOSE_CODE}/steps",
        headers=HDR,
        json={
            "stage": "打样",
            "event_date": "2026-09-15",
            "situation_desc": "同轮修模",
            "is_rework": True,
        },
    )
    assert rework.status_code == 200
    assert rework.json()["data"]["steps"][-1]["round_no"] == 1

    bad = client.post(
        f"/api/crm/samples/{CLOSE_CODE}/steps",
        headers=HDR,
        json={
            "stage": "客户反馈",
            "event_date": "2026-09-16",
            "is_final": True,
            "evidence_text": "",
            "evidence_images": [],
        },
    )
    assert bad.status_code == 400

    ok = client.post(
        f"/api/crm/samples/{CLOSE_CODE}/steps",
        headers=HDR,
        json={
            "stage": "客户反馈",
            "event_date": "2026-09-16",
            "evidence_text": "客户微信确认可量产",
            "evidence_images": ["data:image/png;base64,AAA"],
            "is_final": True,
        },
    )
    assert ok.status_code == 200
    data = client.get(f"/api/crm/samples/{CLOSE_CODE}", headers=HDR).json()["data"]
    assert data["current_stage"] == "结案"
    assert len(data["steps"]) == 3
    last = data["steps"][-1]
    assert last["round_no"] == 1
    assert last["is_final"] is True
    assert last["stage"] == "结案"
    assert last["evidence_text"]
    assert last["evidence_images"]

    blocked = client.post(
        f"/api/crm/samples/{CLOSE_CODE}/steps",
        headers=HDR,
        json={"stage": "打样", "event_date": "2026-09-17", "is_final": False},
    )
    assert blocked.status_code == 400


def test_sample_customer_confirm_does_not_write_due_date():
    client.post("/api/demo/ensure-crm-seed")
    before = client.get("/api/crm/samples/SP-001", headers=HDR).json()["data"]
    due = before["due_date"]
    fail = client.post(
        "/api/crm/samples/SP-001/customer-confirm",
        headers=HDR,
        json={"passed": False, "fail_reason": "", "ship_date": "2026-09-12"},
    )
    assert fail.status_code == 400
    ok = client.post(
        "/api/crm/samples/SP-001/customer-confirm",
        headers=HDR,
        json={"passed": False, "fail_reason": "口味偏甜", "ship_date": "2026-09-12"},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["customer_passed"] == "不通过"
    assert data["fail_reason"] == "口味偏甜"
    assert data["ship_date"] == "2026-09-12"
    assert data["due_date"] == due
    passed = client.post(
        "/api/crm/samples/SP-001/customer-confirm",
        headers=HDR,
        json={"passed": True, "fail_reason": "旧原因", "ship_date": "2026-09-12"},
    )
    assert passed.status_code == 200
    again = passed.json()["data"]
    assert again["customer_passed"] == "通过"
    assert again["fail_reason"] == ""
    assert again["due_date"] == due
