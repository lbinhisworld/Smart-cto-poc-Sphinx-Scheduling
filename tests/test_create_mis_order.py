"""MIS 新建订单 API。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app_factory import app
from api.main import create_app
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from db.snapshot import load_schedule_input
from tests.conftest import ROOT, TODAY

client = TestClient(app)
HDR = {"X-Demo-Role": "SALES", "Content-Type": "application/json"}
PMC = {"X-Demo-Role": "PMC", "Content-Type": "application/json"}


def test_create_mis_order_multi_line():
    client.post("/api/demo/ensure-crm-seed")
    body = {
        "customer_code": "C-001",
        "contract_no": "CT-202609-0001",
        "due_date": "2026-10-01",
        "sales_name": "陈雨桐",
        "lines": [
            {"item_code": "P1", "qty": 10, "unit": "BOX"},
            {"item_code": "P4", "qty": 5, "unit": "BOX"},
        ],
    }
    r = client.post("/api/mis/orders", headers=HDR, json=body)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    order_no = data["order_no"]
    assert data["schedule_phase"] == "PENDING"
    assert data["line_count"] == 2

    rows = client.get("/api/mis/orders?view=pending", headers={"X-Demo-Role": "GM"}).json()["data"]["rows"]
    assert any(x["order_no"] == order_no for x in rows)

    ctp = client.post(
        "/api/crm/ctp?today=2026-09-15",
        headers=HDR,
        json={
            "due_date": "2026-10-01",
            "lines": [
                {"item_code": "P1", "qty": 10, "unit": "BOX"},
                {"item_code": "P4", "qty": 5, "unit": "BOX"},
            ],
        },
    )
    assert ctp.status_code == 200, ctp.text
    lined = ctp.json()["data"]["lines"]
    assert [x["item_code"] for x in lined] == ["P1", "P4"]


def test_create_mis_order_rejects_fractional_qty():
    client.post("/api/demo/ensure-crm-seed")
    r = client.post(
        "/api/mis/orders",
        headers=HDR,
        json={
            "customer_code": "C-001",
            "contract_no": "CT-202609-0001",
            "due_date": "2026-10-01",
            "sales_name": "陈雨桐",
            "lines": [{"item_code": "P1", "qty": 0.401, "unit": "BOX"}],
        },
    )
    assert r.status_code in (400, 422), r.text


def test_mis_multiline_explodes_for_schedule(tmp_path):
    db_path = tmp_path / "mis_explode.db"
    engine = make_engine(db_path)
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, ROOT / "seed" / "seed_data.json")
        session.commit()
    finally:
        session.close()
    app = create_app(factory)
    with TestClient(app) as iso:
        iso.post("/api/demo/ensure-crm-seed")
        created = iso.post(
            "/api/mis/orders",
            headers=HDR,
            json={
                "customer_code": "C-001",
                "contract_no": "CT-202609-0001",
                "due_date": "2026-10-01",
                "sales_name": "陈雨桐",
                "lines": [
                    {"item_code": "P1", "qty": 10, "unit": "BOX"},
                    {"item_code": "P4", "qty": 5, "unit": "BOX"},
                ],
            },
        )
        assert created.status_code == 200, created.text
        order_no = created.json()["data"]["order_no"]
        pool = iso.post(
            "/api/mis/orders/scheduling-pool",
            headers=PMC,
            json={"order_nos": [order_no]},
        )
        assert pool.status_code == 200, pool.text

        s = factory()
        try:
            inp = load_schedule_input(s, today=TODAY, order_nos=[order_no])
            nos = [o.order_no for o in inp.orders]
            assert nos == [f"{order_no}#L1", f"{order_no}#L2"]
            assert [o.item_code for o in inp.orders] == ["P1", "P4"]

            seed = load_schedule_input(s, today=TODAY, order_nos=["SO-001"])
            assert [o.order_no for o in seed.orders] == ["SO-001"]
        finally:
            s.close()

        run = iso.post(
            "/api/schedule/run",
            json={"order_nos": [order_no], "today": TODAY.isoformat(), "reserved_ratio": 0},
        )
        assert run.status_code == 200, run.text
        sources = {w["source_order_no"] for w in run.json()["data"]["result"]["wos"]}
        assert f"{order_no}#L1" in sources
        assert f"{order_no}#L2" in sources
