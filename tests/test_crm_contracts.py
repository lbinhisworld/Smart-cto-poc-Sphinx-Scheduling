"""CRM 合同管理 P1–P4。"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.app_factory import app
from packages.shared.contract_math import money, pending_amount, receipt_would_exceed

client = TestClient(app)
HDR_GM = {"X-Demo-Role": "GM", "Content-Type": "application/json"}
HDR_SALES = {"X-Demo-Role": "SALES", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def _crm_seed():
    client.post("/api/demo/ensure-crm-seed")


def test_contract_math():
    assert pending_amount(money(100), money(30)) == money(70)
    assert receipt_would_exceed(money(100), money(90), money(20)) is True
    assert receipt_would_exceed(money(100), money(90), money(10)) is False


def test_customer_360_contracts_and_payment_summary():
    r = client.get("/api/crm/customers/C-001", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert "payment_summary" in data
    assert "contracts" in data
    assert data["payment_summary"]["received"] >= 0
    assert isinstance(data["contracts"], list)
    if data["contracts"]:
        assert data["contracts"][0].get("contract_no", "").startswith("CT-")


def test_customers_mine_not_shadowed_by_code_route():
    """静态路径 /mine 须先于 /{code} 注册，否则会被当成客户编码返回 404。"""
    r = client.get(
        "/api/crm/customers/mine?today=2026-09-15",
        headers={"X-Demo-Role": "GM"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    assert "items" in body["data"]
    assert "status_counts" in body["data"]


def test_customer_metrics():
    r = client.get("/api/crm/customers/metrics", headers={"X-Demo-Role": "GM"})
    assert r.status_code == 200
    m = r.json()["data"]
    assert m["customer_count"] >= 1
    assert "channel_distribution" in m
    assert "level_distribution" in m
    assert "received_total" in m
    assert "pending_total" in m


def test_create_contract_and_detail():
    body = {
        "customer_code": "C-002",
        "title": "测试框架合同",
        "contract_amount": 50000,
        "status": "ACTIVE",
        "signed_date": "2026-09-01",
        "plans": [
            {
                "line_no": 1,
                "milestone": "签约预付款",
                "condition_type": "ON_SIGN",
                "plan_date": "2026-09-05",
                "plan_amount": 50000,
            }
        ],
    }
    r = client.post("/api/crm/contracts", headers=HDR_GM, json=body)
    assert r.status_code == 200, r.text
    no = r.json()["data"]["contract_no"]
    assert no.startswith("CT-")
    d = client.get(f"/api/crm/contracts/{no}", headers={"X-Demo-Role": "GM"})
    assert d.status_code == 200
    assert d.json()["data"]["title"] == "测试框架合同"
    assert len(d.json()["data"]["plans"]) == 1


def test_receipt_cannot_exceed_contract():
    contracts = client.get(
        "/api/crm/contracts?customer_code=C-001&status=ACTIVE",
        headers={"X-Demo-Role": "GM"},
    ).json()["data"]
    assert contracts
    no = contracts[0]["contract_no"]
    detail = client.get(f"/api/crm/contracts/{no}", headers={"X-Demo-Role": "GM"}).json()["data"]
    cap = Decimal(str(detail["contract_amount"]))
    received = Decimal(str(detail["received_total"]))
    overflow = float(cap - received + 1)
    r = client.post(
        f"/api/crm/contracts/{no}/receipts",
        headers=HDR_GM,
        json={"receipt_date": "2026-09-16", "amount": overflow, "method": "银行"},
    )
    assert r.status_code == 400


def test_mis_order_requires_contract():
    body = {
        "customer_code": "C-001",
        "due_date": "2026-10-05",
        "sales_name": "陈雨桐",
        "lines": [{"item_code": "P1", "qty": 1, "unit": "BOX"}],
    }
    r = client.post("/api/mis/orders", headers=HDR_SALES, json=body)
    assert r.status_code == 422


def test_mis_order_with_contract():
    contracts = client.get(
        "/api/crm/contracts?customer_code=C-001&status=ACTIVE",
        headers={"X-Demo-Role": "GM"},
    ).json()["data"]
    assert contracts
    no = contracts[0]["contract_no"]
    body = {
        "customer_code": "C-001",
        "contract_no": no,
        "due_date": "2026-10-05",
        "sales_name": "陈雨桐",
        "lines": [{"item_code": "P1", "qty": 1, "unit": "BOX"}],
    }
    r = client.post("/api/mis/orders", headers=HDR_SALES, json=body)
    assert r.status_code == 200, r.text
    order_no = r.json()["data"]["order_no"]
    detail = client.get(f"/api/crm/contracts/{no}", headers={"X-Demo-Role": "GM"}).json()["data"]
    assert any(o["order_no"] == order_no for o in detail["orders"])


def test_todos_include_payment_overdue():
    r = client.get("/api/demo/todos", headers={"X-Demo-Role": "FIN"})
    assert r.status_code == 200
    kinds = {t["kind"] for t in r.json()["data"]["items"]}
    assert "PAYMENT_OVERDUE" in kinds
