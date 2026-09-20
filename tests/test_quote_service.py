"""报价状态机、MOQ、转订单快照（禁止默认价 100）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.app_factory import app
from db.demo_crm_seed import ensure_demo_crm
from db.quote_service import (
    approve_quote,
    convert_to_order,
    create_quote,
    submit_quote,
    update_quote,
    void_quote,
)
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from db.tables import CrmQuoteRow, SoOrderLineRow, SoOrderRow
from sqlalchemy import select
from tests.conftest import ROOT, TODAY

client = TestClient(app)
SALES = {"X-Demo-Role": "SALES", "Content-Type": "application/json"}
MGR = {"X-Demo-Role": "SALES_MGR", "Content-Type": "application/json"}


def _session(tmp_path):
    engine = make_engine(tmp_path / "quote.db")
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    import_seed_json(session, ROOT / "seed" / "seed_data.json")
    ensure_demo_crm(session)
    session.commit()
    return session


def _draft_lines(**overrides):
    base = {
        "item_code": "P1",
        "item_name": "巧克力装饰片A",
        "spec": "铲花 24 枚/版",
        "process_label": "手工",
        "category": "插件",
        "unit_price_tax_in": "80.5",
        "moq": 10,
        "qty": 20,
        "uom": "BOX",
        "mold_fee": "500",
        "rebate_qty": 100,
        "rebate_uom": "BOX",
        "note": "含税",
    }
    base.update(overrides)
    return [base]


def test_quote_state_machine_and_moq(tmp_path):
    s = _session(tmp_path)
    try:
        created = create_quote(
            s,
            customer_code="C-001",
            owner_sales="陈雨桐",
            lines=_draft_lines(),
        )
        assert created["status"] == "DRAFT"
        assert created["tax_rate"] == 0.13
        assert created["total_amount"] == 2110.0
        code = created["code"]

        with pytest.raises(ValueError, match="需求量低于起订量"):
            update_quote(s, code, lines=_draft_lines(qty=5, moq=10))

        update_quote(s, code, lines=_draft_lines(qty=12))
        submitted = submit_quote(s, code)
        assert submitted["status"] == "SUBMITTED"
        with pytest.raises(ValueError, match="仅草稿可修改"):
            update_quote(s, code, note="不可改")
        approved = approve_quote(s, code)
        assert approved["status"] == "APPROVED"
        voided = void_quote(s, code)
        assert voided["status"] == "VOID"
    finally:
        s.close()


def test_convert_snapshot_uses_quote_price_not_default_100(tmp_path):
    s = _session(tmp_path)
    try:
        created = create_quote(
            s,
            customer_code="C-001",
            owner_sales="陈雨桐",
            lines=_draft_lines(unit_price_tax_in="88.8", mold_fee="200", qty=10, moq=10),
        )
        submit_quote(s, created["code"])
        approve_quote(s, created["code"])
        out = convert_to_order(
            s,
            quote_code=created["code"],
            contract_no="CT-202609-0001",
            due_date=date(2026, 10, 8),
            today=TODAY,
            sales_name="陈雨桐",
        )
        s.flush()
        order = s.get(SoOrderRow, out["order_no"])
        assert order is not None
        assert order.quote_no == created["code"]
        assert order.due_date == date(2026, 10, 8)
        ln = s.scalars(select(SoOrderLineRow).where(SoOrderLineRow.order_no == out["order_no"])).one()
        assert Decimal(str(ln.unit_price)) == Decimal("88.8")
        assert Decimal(str(ln.unit_price)) != Decimal("100")
        assert Decimal(str(ln.mold_fee)) == Decimal("200")
        assert ln.spec == "铲花 24 枚/版"
        assert ln.note == "含税"
        assert Decimal(str(ln.line_amount)) == Decimal("1088.00")
        head = s.get(CrmQuoteRow, created["code"])
        assert head.status == "CONVERTED"
        assert head.order_no == out["order_no"]
        with pytest.raises(ValueError, match="仅已批准"):
            convert_to_order(
                s,
                quote_code=created["code"],
                contract_no="CT-202609-0001",
                due_date=date(2026, 10, 8),
                today=TODAY,
            )
    finally:
        s.close()


def test_convert_rejects_missing_item_code(tmp_path):
    s = _session(tmp_path)
    try:
        created = create_quote(
            s,
            customer_code="C-001",
            lines=[
                {
                    "item_code": None,
                    "item_name": "新品打样",
                    "unit_price_tax_in": "10",
                    "qty": 2,
                    "uom": "BOX",
                }
            ],
        )
        submit_quote(s, created["code"])
        approve_quote(s, created["code"])
        with pytest.raises(ValueError, match="已入库成品品项"):
            convert_to_order(
                s,
                quote_code=created["code"],
                contract_no="CT-202609-0001",
                due_date=date(2026, 10, 1),
                today=TODAY,
            )
    finally:
        s.close()


def test_quote_api_moq_and_from_quote():
    client.post("/api/demo/ensure-crm-seed")
    created = client.post(
        "/api/crm/quotes",
        headers=SALES,
        json={
            "customer_code": "C-001",
            "owner_sales": "陈雨桐",
            "lines": [
                {
                    "item_code": "P2",
                    "item_name": "卡通造型件B",
                    "unit_price_tax_in": "77",
                    "moq": 8,
                    "qty": 8,
                    "uom": "BOX",
                    "mold_fee": 0,
                    "spec": "API 转单",
                    "note": "快照",
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    code = created.json()["data"]["code"]

    bad = client.put(
        f"/api/crm/quotes/{code}",
        headers=SALES,
        json={"lines": [{"item_code": "P2", "qty": 3, "moq": 8, "unit_price_tax_in": "77"}]},
    )
    assert bad.status_code == 400, bad.text

    assert client.post(f"/api/crm/quotes/{code}/submit", headers=SALES).status_code == 200
    assert client.post(f"/api/crm/quotes/{code}/approve", headers=SALES).status_code == 403
    assert client.post(f"/api/crm/quotes/{code}/approve", headers=MGR).status_code == 200

    conv = client.post(
        "/api/mis/orders/from-quote?today=2026-09-15",
        headers=SALES,
        json={
            "quote_code": code,
            "contract_no": "CT-202609-0001",
            "due_date": "2026-10-12",
            "sales_name": "陈雨桐",
        },
    )
    assert conv.status_code == 200, conv.text
    data = conv.json()["data"]
    assert data["quote_code"] == code
    detail = client.get(
        f"/api/mis/orders/{data['order_no']}",
        headers={"X-Demo-Role": "GM"},
    )
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["quote_no"] == code
    ln = body["lines"][0]
    assert ln["unit_price"] == 77
    assert ln["spec"] == "API 转单"
    assert ln["note"] == "快照"
