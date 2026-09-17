"""PMC 发起协商交期：销售回日不写锚；PMC 改锚；企微 S6–S8。"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from api.main import create_app
from db.due_negotiate import classify_due_gap, render_brief_text
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from db.tables import SoOrderRow
from tests.conftest import ROOT, TODAY

PMC = {"X-Demo-Role": "PMC", "Content-Type": "application/json"}
SALES = {"X-Demo-Role": "SALES", "Content-Type": "application/json"}


def _brief_kwargs(**over):
    base = dict(
        order_no="SO-S004",
        customer="云顶精选酒店集采",
        sales_name="王芷若",
        item_code="P6",
        old_due=date(2026, 10, 8),
        suggested_due=date(2026, 9, 22),
        reason="未在最早可排日前安置完",
    )
    base.update(over)
    return base


def test_classify_due_gap():
    assert classify_due_gap(date(2026, 10, 8), date(2026, 9, 22)) == "FEASIBLE"
    assert classify_due_gap(date(2026, 9, 22), date(2026, 9, 22)) == "FEASIBLE"
    assert classify_due_gap(date(2026, 9, 22), date(2026, 9, 24)) == "LATE"


def test_brief_feasible_does_not_ask_sales_to_change_due():
    text = render_brief_text(**_brief_kwargs())
    assert "10/8" in text
    assert "9/22" in text
    assert "改为不早于" not in text
    assert "挂红" not in text
    assert "交期本身够" in text
    assert "不要找销售改交期" in text


def test_brief_late_still_asks_to_delay():
    text = render_brief_text(
        **_brief_kwargs(
            old_due=date(2026, 9, 22),
            suggested_due=date(2026, 9, 24),
            reason="半成品来不及",
        )
    )
    assert "建议交付不早于 9/24" in text
    assert "必须开" in text and "补齐缺口" in text
    assert "仍按 9/22 挂红" in text
    assert "无法满足 9/22 交付" in text


def _client(tmp_path):
    engine = make_engine(tmp_path / "due_neg.db")
    init_db(engine)
    factory = session_factory(engine)
    s = factory()
    try:
        import_seed_json(s, ROOT / "seed" / "seed_data.json")
        s.commit()
    finally:
        s.close()
    return TestClient(create_app(factory)), factory


def test_brief_and_reply_do_not_write_due_date(tmp_path):
    client, factory = _client(tmp_path)
    due_before = date(2026, 9, 22)

    preview = client.post(
        "/api/schedule/assist/brief/preview",
        headers=PMC,
        json={
            "order_no": "SO-004",
            "suggested_due": "2026-09-24",
            "conflict_code": "E2",
            "reason": "半成品来不及",
        },
    )
    assert preview.status_code == 200, preview.text
    assert "9/24" in preview.json()["data"]["brief_text"] or "2026-09-24" in preview.json()["data"]["brief_text"]
    assert "SO-004" in preview.json()["data"]["brief_text"]

    sent = client.post(
        "/api/schedule/assist/brief",
        headers=PMC,
        json={
            "order_no": "SO-004",
            "suggested_due": "2026-09-24",
            "conflict_code": "E2",
            "reason": "半成品来不及",
            "run_id": "run-demo",
        },
    )
    assert sent.status_code == 200, sent.text
    req_id = sent.json()["data"]["id"]
    assert sent.json()["data"]["status"] == "PENDING_SALES"

    s = factory()
    try:
        assert s.get(SoOrderRow, "SO-004").due_date == due_before
    finally:
        s.close()

    sales_wx = client.get("/api/wecom/messages?limit=50", headers={"X-Demo-Role": "SALES"}).json()["data"]
    assert any(m.get("scene") == "S6" or "协商交期" in (m.get("title") or "") for m in sales_wx)

    todos = client.get("/api/demo/todos", headers={"X-Demo-Role": "SALES"}).json()["data"]["items"]
    assert any(t["kind"] == "DUE_NEGOTIATE" and "SO-004" in t["title"] for t in todos)

    reply = client.post(
        f"/api/orders/SO-004/due-negotiate/reply",
        headers=SALES,
        json={"proposed_due": "2026-09-24", "request_id": req_id},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["data"]["status"] == "SALES_REPLIED"

    s = factory()
    try:
        assert s.get(SoOrderRow, "SO-004").due_date == due_before
    finally:
        s.close()

    pmc_wx = client.get("/api/wecom/messages?limit=50", headers={"X-Demo-Role": "PMC"}).json()["data"]
    assert any(m.get("scene") == "S7" or "已回" in (m.get("title") or "") for m in pmc_wx)

    apply = client.post(
        f"/api/orders/SO-004/due-negotiate/apply",
        headers=PMC,
        json={"request_id": req_id, "today": TODAY.isoformat()},
    )
    assert apply.status_code == 200, apply.text
    assert apply.json()["data"]["status"] == "APPROVED"

    s = factory()
    try:
        assert s.get(SoOrderRow, "SO-004").due_date == date(2026, 9, 24)
    finally:
        s.close()

    both = client.get("/api/wecom/messages?limit=50", headers={"X-Demo-Role": "SALES"}).json()["data"]
    assert any(m.get("scene") == "S8" or "改锚" in (m.get("title") or "") for m in both)

    ev = client.get("/api/orders/SO-004/due-events", headers=PMC).json()["data"]["events"]
    types = [e["event_type"] for e in ev]
    assert "CONFLICT_FOUND" in types
    assert "SALES_BRIEF_SENT" in types
    assert "SALES_REPLIED" in types
    assert "DUE_APPLIED" in types


def test_sales_cannot_apply_due_anchor(tmp_path):
    client, _ = _client(tmp_path)
    sent = client.post(
        "/api/schedule/assist/brief",
        headers=PMC,
        json={
            "order_no": "SO-004",
            "suggested_due": "2026-09-24",
            "conflict_code": "E2",
            "reason": "半成品来不及",
        },
    )
    req_id = sent.json()["data"]["id"]
    client.post(
        "/api/orders/SO-004/due-negotiate/reply",
        headers=SALES,
        json={"proposed_due": "2026-09-24", "request_id": req_id},
    )
    r = client.post(
        "/api/orders/SO-004/due-negotiate/apply",
        headers=SALES,
        json={"request_id": req_id, "today": TODAY.isoformat()},
    )
    assert r.status_code == 403


def test_preview_feasible_flags_cannot_negotiate(tmp_path):
    client, _ = _client(tmp_path)
    preview = client.post(
        "/api/schedule/assist/brief/preview",
        headers=PMC,
        json={
            "order_no": "SO-004",
            "suggested_due": "2026-09-20",
            "conflict_code": "E1",
            "reason": "未在最早可排日前安置完",
        },
    )
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    assert data["due_gap"] == "FEASIBLE"
    assert data["can_negotiate"] is False
    assert "改为不早于" not in data["brief_text"]
    assert "交期本身够" in data["brief_text"]


def test_send_rejects_when_fastest_not_after_customer_due(tmp_path):
    client, _ = _client(tmp_path)
    sent = client.post(
        "/api/schedule/assist/brief",
        headers=PMC,
        json={
            "order_no": "SO-004",
            "suggested_due": "2026-09-20",
            "conflict_code": "E1",
            "reason": "未在最早可排日前安置完",
        },
    )
    assert sent.status_code == 409
    assert "不必找销售" in (sent.json().get("detail") or "")
