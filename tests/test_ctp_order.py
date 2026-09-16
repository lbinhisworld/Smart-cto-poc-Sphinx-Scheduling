"""整单 CTP：多行同池一次倒排，不落库。"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from api.app_factory import app

client = TestClient(app)
HDR = {"X-Demo-Role": "SALES"}
TODAY = "2026-09-15"


def test_ctp_order_two_lines_one_run_no_persist():
    r = client.post(
        f"/api/crm/ctp?today={TODAY}",
        headers=HDR,
        json={
            "due_date": "2026-09-28",
            "lines": [
                {"item_code": "P1", "qty": 2, "unit": "BOX"},
                {"item_code": "P1L", "qty": 3, "unit": "BOX"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "feasible" in body
    assert body["requested_due"] == "2026-09-28"
    lines = body["lines"]
    assert [ln["item_code"] for ln in lines] == ["P1", "P1L"]
    assert all("feasible" in ln for ln in lines)
    assert body["feasible"] is all(ln["feasible"] for ln in lines)
    assert "整单" in (body.get("note") or "") or "同池" in (body.get("note") or "")
    sales = body.get("sales") or {}
    assert sales.get("headline")
    assert sales.get("can_meet_due_date") is body["feasible"]

    leaked = client.get("/api/mis/orders?view=all", headers={"X-Demo-Role": "GM"})
    assert leaked.status_code == 200
    nos = [x["order_no"] for x in leaked.json()["data"]["rows"]]
    assert not any(str(n).startswith("CTP-TRY") for n in nos)


def test_ctp_order_all_red_makes_order_infeasible():
    r = client.post(
        f"/api/crm/ctp?today={TODAY}",
        headers=HDR,
        json={
            "due_date": "2026-09-16",
            "lines": [
                {"item_code": "P2", "qty": 200, "unit": "BOX"},
                {"item_code": "P5", "qty": 200, "unit": "BOX"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["feasible"] is False
    assert body["sales"]["status"] == "late"
    assert any(not ln["feasible"] for ln in body["lines"])


def test_ctp_rejects_fractional_qty():
    r = client.post(
        f"/api/crm/ctp?today={TODAY}",
        headers=HDR,
        json={
            "due_date": "2026-09-28",
            "lines": [{"item_code": "P1", "qty": 1.5, "unit": "BOX"}],
        },
    )
    assert r.status_code in (400, 422), r.text


def test_ctp_single_item_still_works_via_lines_wrapper():
    r = client.post(
        f"/api/crm/ctp?today={TODAY}",
        headers=HDR,
        json={"item_code": "P4", "qty_order": 60, "unit": "BOX", "due_date": "2026-09-24"},
    )
    assert r.status_code == 200
    assert "feasible" in r.json()["data"]
