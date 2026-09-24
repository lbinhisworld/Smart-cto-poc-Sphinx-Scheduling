"""订单多行明细（MIS）。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)
HDR = {"X-Demo-Role": "GM"}


def test_official_seed_orders_stay_single_item():
    """官方 12 单以表头为准。明细不得再抄进其他单的品项。"""
    client.post("/api/demo/ensure-crm-seed")
    rows = client.get("/api/mis/orders?view=all", headers=HDR).json()["data"]["rows"]
    official_nos = {
        "SO-001",
        "SO-002",
        "SO-003",
        "SO-004",
        "SO-005",
        "SO-101",
        "SO-102",
        "SO-201",
        "SO-202",
        "SO-301",
        "SO-302",
        "SO-303",
    }
    official = [r for r in rows if r["order_no"] in official_nos]
    assert len(official) == 12
    assert all(r["line_count"] == 1 for r in official)
    so2 = next(x for x in official if x["order_no"] == "SO-002")
    assert so2["lines_summary"].startswith("P2×")
    assert "P5" not in so2["lines_summary"]
    assert "P6" not in so2["lines_summary"]
