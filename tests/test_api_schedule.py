"""阶段 4 HTTP 集成测试（httpx TestClient）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.plan_store import current_plan_version
from db.repositories import get_order_due_date
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from engine.models import ScheduleResult
from engine.schedule import schedule
from tests.conftest import ROOT, TODAY, build_schedule_input, load_seed
from tests.helpers import semi_wo_of, tasks_of


def _tasks_from_payload(payload: dict, item_code: str) -> list[tuple[str, int]]:
    wo_nos = {w["wo_no"] for w in payload["wos"] if w["item_code"] == item_code}
    rows = [
        (t["task_date"], t["qty_board"])
        for t in payload["tasks"]
        if t["wo_no"] in wo_nos
    ]
    return sorted(rows)


@pytest.fixture
def api_client(tmp_path):
    db_path = tmp_path / "api_test.db"
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
    with TestClient(app) as client:
        yield client, factory


def _run_body(order_nos=None):
    return {
        "order_nos": order_nos or ["SO-001", "SO-002", "SO-003"],
        "today": TODAY.isoformat(),
        "reserved_ratio": 0.0,
    }


def test_api_run_three_orders_matches_engine(api_client):
    client, _ = api_client
    resp = client.post("/api/schedule/run", json=_run_body())
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["plan_version"] == 1

    payload = body["data"]["result"]
    seed = load_seed()
    core = ["SO-001", "SO-002", "SO-003"]
    expected = schedule(
        build_schedule_input(
            seed, today=TODAY, reserved_ratio=Decimal("0"), order_nos=core
        )
    )
    for code in ("P1", "P2", "P4", "S2"):
        exp = [(d.isoformat(), q) for d, q in tasks_of(expected, code)]
        assert _tasks_from_payload(payload, code) == exp
    assert semi_wo_of(expected, "SO-002").qty_board_plan == 282


def test_api_cell_detail_task_and_cell(api_client):
    client, _ = api_client
    run = client.post("/api/schedule/run", json=_run_body()).json()["data"]
    task = next(
        t
        for t in run["result"]["tasks"]
        if t["group_code"] == "MANUAL" and t.get("dept", "FINISHED_DEPT") == "FINISHED_DEPT"
    )
    resp = client.post(
        "/api/plan/cell-detail",
        json={
            "today": TODAY.isoformat(),
            "dept": task.get("dept", "FINISHED_DEPT"),
            "group_code": "MANUAL",
            "task_date": task["task_date"],
            "focus_task_id": task["task_id"],
            "plan_version": run["plan_version"],
            "tasks": run["result"]["tasks"],
            "reserved_ratio": 0,
        },
    )
    assert resp.status_code == 200
    detail = resp.json()["data"]
    assert detail["focus_task_id"] == task["task_id"]
    assert detail["task_metrics"] is not None
    assert detail["orders"][0]["customer"]
    cell_only = client.get(
        "/api/plan/cell-detail",
        params={
            "today": TODAY.isoformat(),
            "dept": task.get("dept", "FINISHED_DEPT"),
            "group_code": "MANUAL",
            "task_date": task["task_date"],
            "version": run["plan_version"],
        },
    ).json()["data"]
    assert cell_only["task_metrics"] is None
    assert len(cell_only["tasks"]) >= 1


def test_api_what_if_does_not_bump_version(api_client):
    client, _ = api_client
    client.post("/api/schedule/run", json=_run_body())
    resp = client.post("/api/schedule/what-if", json=_run_body())
    data = resp.json()["data"]
    assert data["plan_version_unchanged"] is True
    assert data["plan_version"] == 1


def test_api_apply_bumps_plan_version(api_client):
    client, factory = api_client
    client.post("/api/schedule/run", json=_run_body())
    resp = client.post("/api/schedule/apply", json=_run_body())
    assert resp.json()["data"]["plan_version"] == 2
    with factory() as session:
        assert current_plan_version(session) == 2


def test_api_schedule_never_writes_order_due_date(api_client):
    client, factory = api_client
    with factory() as session:
        before = get_order_due_date(session, "SO-002")
    client.post("/api/schedule/run", json=_run_body())
    with factory() as session:
        after = get_order_due_date(session, "SO-002")
    assert before == after == date(2026, 10, 7)


def test_api_user_patch_due_then_run_has_e2(api_client):
    client, _ = api_client
    client.patch("/api/orders/SO-002", json={"due_date": "2026-09-23"})
    resp = client.post("/api/schedule/run", json=_run_body())
    conflicts = resp.json()["data"]["result"]["conflicts"]
    assert any(c["code"] == "E2" for c in conflicts)
    due = client.get("/api/orders/SO-002").json()["data"]["due_date"]
    assert due == "2026-09-23"


def test_api_list_orders(api_client):
    client, _ = api_client
    resp = client.get("/api/orders")
    assert resp.status_code == 200
    data = resp.json()["data"]
    orders = data["orders"]
    nos = {o["order_no"] for o in orders}
    assert nos >= {"SO-001", "SO-002", "SO-003"}
    assert len(nos) == 12
    so001 = next(o for o in orders if o["order_no"] == "SO-001")
    assert so001.get("sales_name") == "陈雨桐"
    assert data["orders_in_db"] == 12
    assert data["seed_sync"]["order_count"] == 12


def test_api_dev_import_seed_realoads(api_client):
    client, factory = api_client
    from sqlalchemy import delete

    from db.tables import SoOrderRow

    with factory() as session:
        session.execute(delete(SoOrderRow).where(SoOrderRow.order_no == "SO-101"))
        session.commit()
    resp = client.post("/api/dev/import-seed", json={})
    assert resp.status_code == 200
    assert resp.json()["data"]["orders_in_db"] == 12
    assert len(client.get("/api/orders").json()["data"]["orders"]) == 12


def test_api_plan_get_after_run(api_client):
    client, _ = api_client
    client.post("/api/schedule/run", json=_run_body())
    resp = client.get("/api/plan")
    assert resp.json()["data"]["plan_version"] == 1
    assert resp.json()["data"]["result"]["tasks"]


def test_api_conflicts_get_matches_run(api_client):
    client, _ = api_client
    client.patch("/api/orders/SO-002", json={"due_date": "2026-09-23"})
    run_conflicts = client.post("/api/schedule/run", json=_run_body()).json()["data"]["result"][
        "conflicts"
    ]
    got = client.get("/api/conflicts").json()["data"]
    assert got["plan_version"] == 1
    assert got["conflicts"] == run_conflicts


def test_api_plan_diff_after_apply(api_client):
    client, _ = api_client
    client.post("/api/schedule/run", json=_run_body())
    client.post("/api/schedule/apply", json=_run_body())
    resp = client.get(
        "/api/plan/diff",
        params={"from_version": 1, "to_version": 2, "today": TODAY.isoformat()},
    )
    assert resp.status_code == 200
    assert "diff" in resp.json()["data"]


def test_api_insert_trial_and_apply(api_client):
    client, factory = api_client
    client.post("/api/schedule/run", json=_run_body())
    insert_no = "SO-991"
    new_order = {
        "order_no": insert_no,
        "customer": "插单客户",
        "item_code": "P1",
        "qty_order": 50,
        "unit": "BOX",
        "due_date": "2026-09-22",
        "ready_date": TODAY.isoformat(),
        "customer_level": 5,
        "amount": 5000,
        "is_urgent": True,
    }
    assert client.post("/api/orders", json=new_order).status_code == 200
    trial = client.post(
        "/api/schedule/insert",
        json={"order_no": insert_no, "today": TODAY.isoformat(), "reason": "催单"},
    )
    assert trial.status_code == 200
    data = trial.json()["data"]
    assert len(data["strategies"]) == 4
    assert data["feasibility"]["status"] in ("OK", "OK_WITH_WARN")

    apply_resp = client.post(
        "/api/schedule/insert/apply",
        json={
            "order_no": insert_no,
            "today": TODAY.isoformat(),
            "strategy": "B",
            "reason": "催单",
            "requester": "pytest",
        },
    )
    assert apply_resp.status_code == 200
    assert apply_resp.json()["data"]["plan_version"] == 2

    from sqlalchemy import select

    from db.tables import WoInsertLogRow

    with factory() as session:
        row = session.scalar(
            select(WoInsertLogRow).where(
                WoInsertLogRow.strategy == "B",
                WoInsertLogRow.reason == "催单",
            )
        )
        assert row is not None
        assert insert_no in row.wo_no
        assert row.strategy == "B"
        assert row.plan_version_before == 1
        assert row.plan_version_after == 2
