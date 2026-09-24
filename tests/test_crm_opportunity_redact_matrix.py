"""§5.4 商机详情 · 角色 × 列 redact 回归。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)

ROLES = {
    "SALES": {"X-Demo-Role": "SALES"},
    "SALES_ASSIST": {"X-Demo-Role": "SALES_ASSIST"},
    "SALES_MGR": {"X-Demo-Role": "SALES_MGR"},
    "RD": {"X-Demo-Role": "RD"},
    "FIN": {"X-Demo-Role": "FIN"},
    "GM": {"X-Demo-Role": "GM"},
}


@pytest.fixture(scope="function")
def opp_id() -> int:
    client.post("/api/demo/ensure-crm-seed")
    opps = client.get("/api/crm/opportunities", headers=ROLES["GM"]).json()["data"]
    row = next(r for r in opps if "好利来加急" in r["name"])
    return int(row["id"])


def _detail(role: str, opp_id: int) -> dict:
    r = client.get(f"/api/crm/opportunities/{opp_id}", headers=ROLES[role])
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_sales_redact(opp_id: int):
    d = _detail("SALES", opp_id)
    assert d.get("visit_text")
    assert "sample_cost" not in d
    assert "internal_quote" not in d
    assert d["customer_quote"]["amount"]
    assert "received" not in (d.get("sign") or {})


def test_sales_assist_redact(opp_id: int):
    d = _detail("SALES_ASSIST", opp_id)
    assert "sample_cost" not in d
    sign = d.get("sign") or {}
    assert sign.get("contract_amount")


def test_sales_mgr_redact(opp_id: int):
    d = _detail("SALES_MGR", opp_id)
    assert d["customer_quote"]["amount"]
    assert "sample_cost" not in d


def test_rd_redact(opp_id: int):
    d = _detail("RD", opp_id)
    assert "visit_text" not in d
    assert "customer_quote" not in d
    assert d["sample_cost"]["material"]
    assert "对客报价" not in (d.get("column_status") or {})


def test_fin_redact(opp_id: int):
    d = _detail("FIN", opp_id)
    assert "visit_text" not in d
    assert d["internal_quote"]["gap"]
    assert d["customer_quote"]["amount"]


def test_gm_sees_money_and_visit(opp_id: int):
    d = _detail("GM", opp_id)
    assert d.get("visit_text")
    assert d.get("sample_cost")
    assert d.get("internal_quote")
    assert d["customer_quote"]["amount"]
