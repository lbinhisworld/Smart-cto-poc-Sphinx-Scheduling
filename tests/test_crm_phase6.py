"""Phase 6：CRM 漏斗 + CTP + 变更 + 企微模拟。"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)


def test_funnel_seed_nonzero():
    r = client.get("/api/crm/reports/funnel", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] >= 6
    assert sum(data["counts"].values()) == data["total"]


def test_ctp_returns_feasibility():
    r = client.post(
        "/api/crm/ctp",
        headers={"X-Demo-Role": "SALES"},
        json={"item_code": "P4", "qty_order": 60, "unit": "BOX", "due_date": "2026-09-24"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert "feasible" in body
    assert body.get("requested_due") == "2026-09-24"
    sales = body.get("sales") or {}
    assert sales.get("headline")
    assert sales.get("can_meet_due_date") is body["feasible"]


def test_ctp_arbitrary_item_without_template_order():
    r = client.post(
        "/api/crm/ctp",
        headers={"X-Demo-Role": "SALES"},
        json={"item_code": "P1", "qty_order": 80, "unit": "BOX", "due_date": "2026-09-28"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert "feasible" in body
    assert body.get("requested_due") == "2026-09-28"
    assert "CTP-TRY" in (body.get("note") or "")


def test_ctp_sales_brief_infeasible_has_earliest_and_materials():
    r = client.post(
        "/api/crm/ctp",
        headers={"X-Demo-Role": "SALES"},
        json={"item_code": "P2", "qty_order": 200, "unit": "BOX", "due_date": "2026-09-28"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["feasible"] is False
    sales = body["sales"]
    assert sales["status"] == "late"
    assert sales.get("earliest_delivery")
    assert any(m.get("status") == "need_make" for m in sales.get("materials") or [])
    assert body.get("earliest_delivery") == sales.get("earliest_delivery")


def test_order_change_flow_and_wecom():
    submit = client.post(
        "/api/order-changes",
        headers={"X-Demo-Role": "SALES"},
        json={"order_no": "SO-002", "new_due": "2026-09-20"},
    )
    assert submit.status_code == 200
    req_id = submit.json()["data"]["id"]
    impact = client.get("/api/order-changes", headers={"X-Demo-Role": "PMC"}).json()["data"]
    assert any(x["id"] == req_id and x["impact"].get("order_no") == "SO-002" for x in impact)

    msgs_before = len(client.get("/api/wecom/messages?limit=100", headers={"X-Demo-Role": "PMC"}).json()["data"])
    approve = client.post(
        f"/api/order-changes/{req_id}/approve",
        headers={"X-Demo-Role": "PMC"},
    )
    assert approve.status_code == 200
    msgs_after = client.get("/api/wecom/messages?limit=100", headers={"X-Demo-Role": "PMC"}).json()["data"]
    assert len(msgs_after) >= msgs_before + 1

    due = client.get("/api/orders/SO-002").json()["data"]["due_date"]
    assert due == "2026-09-20"


def test_wecom_schedule_idempotent():
    from apps.api.services import flow as flow_service
    from db.session import make_engine, session_factory, init_db
    from db.migrate import ensure_schema
    from pathlib import Path
    from datetime import datetime, UTC

    db_path = Path(__file__).resolve().parents[1] / "data" / "scheduling_test_wecom.db"
    if db_path.is_file():
        db_path.unlink()
    engine = make_engine(db_path)
    init_db(engine)
    ensure_schema(engine)
    s = session_factory(engine)()
    key = "test-idem-1"
    t = datetime.now(UTC)
    a = flow_service.emit_schedule_event(
        s, scene="S2", title="t", start_at=t, deep_link="/schedule", idempotency_key=key
    )
    b = flow_service.emit_schedule_event(
        s, scene="S2", title="t2", start_at=t, deep_link="/schedule", idempotency_key=key
    )
    s.commit()
    assert a is not None and b is not None
    assert a.id == b.id
    s.close()
    if db_path.is_file():
        db_path.unlink()
