"""移动端确认拜访 · 匹配负责人线索并写跟进。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)
SALES = {"X-Demo-Role": "SALES"}
MGR = {"X-Demo-Role": "SALES_MGR"}


def test_confirm_visit_links_lead_by_company_name():
    client.post("/api/demo/ensure-crm-seed")
    leads = client.get("/api/crm/leads?pool=false&today=2026-09-15", headers=MGR).json()["data"]
    mine = next((row for row in leads if row.get("owner_sales") == "李业务"), None)
    if mine is None:
        mine = next((row for row in leads if row.get("company_name")), None)
    assert mine is not None, "需要李业务名下至少一条线索"
    company = mine["company_name"]
    detail = client.get(f"/api/crm/leads/{mine['code']}", headers=SALES).json()["data"]
    n_before = len(detail["follow_records"])

    resp = client.post(
        "/api/crm/visits/confirm",
        headers=SALES,
        json={
            "customer_name": company,
            "visit_kind": "现有客户",
            "narrative": "第二次现场沟通",
            "outcome": "关系建联",
            "next_step": "约见决策人",
            "next_date": "2026-09-20",
            "check_in_at": "2026-09-15T14:00:00",
            "check_out_at": "2026-09-15T14:25:00",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["is_valid"] is True

    after = client.get(f"/api/crm/leads/{mine['code']}", headers=SALES).json()["data"]
    assert len(after["follow_records"]) >= n_before + 1
    assert any("第二次现场沟通" in (r["content"] or "") for r in after["follow_records"])
