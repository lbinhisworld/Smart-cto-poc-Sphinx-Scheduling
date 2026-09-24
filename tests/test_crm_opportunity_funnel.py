"""商机列表顶栏漏斗 · 角色范围与阶段口径。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)

GM = {"X-Demo-Role": "GM"}
SALES = {"X-Demo-Role": "SALES"}


def _funnel(headers: dict) -> dict:
    client.post("/api/demo/ensure-crm-seed")
    r = client.get("/api/crm/opportunities/funnel", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_funnel_stages_and_conversion_math():
    data = _funnel(GM)
    stages = [s["stage"] for s in data["steps"]]
    assert stages == ["尚未打样", "打样中", "方案报价", "已签单"]
    counts = {s["stage"]: s["count"] for s in data["steps"]}
    assert counts["尚未打样"] >= counts["打样中"] >= counts["方案报价"] >= counts["已签单"]
    for i, step in enumerate(data["steps"][:-1]):
        nxt = data["steps"][i + 1]
        if step["count"]:
            assert step["to_next_pct"] == round(nxt["count"] * 100 / step["count"])
    assert data["scope"] == "all"


def test_sales_sees_own_scope_and_subset():
    gm = _funnel(GM)
    mine = _funnel(SALES)
    assert mine["scope"] == "my"
    assert mine["steps"][0]["count"] <= gm["steps"][0]["count"]
