"""M9 品控台账。"""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from api.app_factory import app
from db.qc_period import month_key, period_fields, week_no_iso
from db.qc_verdict import compute_product_verdict, compute_swab_verdict, validate_override

client = TestClient(app)
HDR_QC = {"X-Demo-Role": "QC"}
HDR_GM = {"X-Demo-Role": "GM"}


def test_period_fields_br_qc_04():
    d = date(2026, 9, 15)
    pf = period_fields(d)
    assert pf["month_key"] == "2026-09"
    assert pf["week_no"] == week_no_iso(d)
    assert pf["weekday"] == "周二"
    assert month_key(d) == "2026-09"


def test_verdict_swab_and_product():
    v, reason = compute_swab_verdict(tpc_cfu_ml="50", coliform_cfu_ml="5")
    assert v == "PASS"
    assert reason == ""
    v2, _ = compute_swab_verdict(tpc_cfu_ml="150", coliform_cfu_ml="5")
    assert v2 == "FAIL"
    v3, _ = compute_swab_verdict(tpc_cfu_ml="<10", coliform_cfu_ml="5")
    assert v3 == "PASS"
    pv, _ = compute_product_verdict(moisture_pct="7", coliform_cfu_g="5", tpc_cfu_g="100")
    assert pv == "PASS"


def test_override_requires_reason():
    try:
        validate_override(computed="FAIL", final="PASS", override_reason="")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "BR-QC-06" in str(exc)


def test_kingdee_master_sync_and_receipt_br_qc_02():
    r = client.post("/api/kingdee/sync-suppliers", headers=HDR_GM)
    assert r.status_code == 200
    r2 = client.post("/api/kingdee/sync-raw-materials", headers=HDR_GM)
    assert r2.status_code == 200

    bad = client.post(
        "/api/qc/receipts",
        headers=HDR_QC,
        json={
            "incoming_date": "2026-09-12",
            "supplier_code": "NO-SUCH",
            "material_code": "RM-COCOA-70",
            "qty": 10,
        },
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/qc/receipts",
        headers=HDR_QC,
        json={
            "incoming_date": "2026-09-12",
            "supplier_code": "SUP-001",
            "material_code": "RM-COCOA-70",
            "qty": 10,
            "batch_no": "T-BATCH-1",
        },
    )
    assert ok.status_code == 200
    rid = ok.json()["data"]["id"]

    ex = client.post(
        "/api/qc/exceptions",
        headers=HDR_QC,
        json={"receipt_id": rid, "phenomenon": "测试异常"},
    )
    assert ex.status_code == 200
    eid = ex.json()["data"]["id"]

    tr = client.post(
        f"/api/qc/exceptions/{eid}/transition",
        headers=HDR_QC,
        json={"action": "start"},
    )
    assert tr.status_code == 200
    assert tr.json()["data"]["status"] == "IN_PROGRESS"

    bad_tr = client.post(
        f"/api/qc/exceptions/{eid}/transition",
        headers=HDR_QC,
        json={"action": "not_a_valid_action"},
    )
    assert bad_tr.status_code == 400


def test_attachments_and_swab_test():
    att = client.post(
        "/api/qc/attachments",
        headers=HDR_QC,
        json={
            "entity_type": "MATERIAL_EXCEPTION",
            "entity_id": 1,
            "items": [{"storage_ref": "data:image/png;base64,AAA", "file_name": "a.png"}],
        },
    )
    assert att.status_code == 200
    assert len(att.json()["data"]) >= 1

    points = client.get("/api/qc/swab-points", headers=HDR_QC).json()["data"]
    assert points
    st = client.post(
        "/api/qc/swab-tests",
        headers=HDR_QC,
        json={
            "point_id": points[0]["id"],
            "experiment_date": "2026-09-14",
            "sampling_date": "2026-09-14",
            "tpc_cfu_ml": "200",
            "coliform_cfu_ml": "1",
        },
    )
    assert st.status_code == 200
    assert st.json()["data"]["verdict_computed"] == "FAIL"


def test_qc_summary_and_export():
    s = client.get("/api/qc/summary", headers=HDR_QC)
    assert s.status_code == 200
    assert "receipts_mtd" in s.json()["data"]
    exp = client.get("/api/qc/export/receipts", headers=HDR_QC)
    assert exp.status_code == 200
    assert b"\xe6\x9c\x88\xe4\xbb\xbd" in exp.content or b"month" in exp.content.lower() or len(exp.content) > 10
