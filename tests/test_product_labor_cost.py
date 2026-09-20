"""C 链路：按成品品项汇总计划人工成本。"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.product_labor_cost import (
    header_order_no,
    is_sample_cost_source,
    planned_labor_cost_by_product,
)
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from db.tables import (
    CrmQuoteRow,
    PlanVersionRow,
    SoOrderRow,
    WoRow,
    WoTaskRow,
)
from tests.conftest import ROOT, TODAY


@pytest.fixture
def scheduled_client(tmp_path):
    db_path = tmp_path / "labor_prod.db"
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
        client.post(
            "/api/schedule/run",
            json={"order_nos": ["SO-001", "SO-002"], "today": TODAY.isoformat(), "reserved_ratio": 0},
        )
        yield client


HDR = {"X-Demo-Role": "GM"}


def test_planned_labor_by_product_after_schedule(scheduled_client):
    client = scheduled_client
    resp = client.get("/api/hr/labor-cost/by-product", headers=HDR)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["plan_version"] > 0
    assert data["totals"]["hours_man"] > 0
    codes = {p["item_code"] for p in data["products"]}
    assert "P1" in codes or "P2" in codes
    assert "sample_excluded" in data
    assert data["sample_excluded"]["hours_man"] == 0


def test_header_order_no_strips_line_suffix():
    assert header_order_no("SO-SMP-1#L2") == "SO-SMP-1"
    assert header_order_no("SO-001") == "SO-001"


def test_is_sample_cost_source_covers_aliases():
    assert is_sample_cost_source("SAMPLE")
    assert is_sample_cost_source("rnd")
    assert is_sample_cost_source("R&D")
    assert not is_sample_cost_source("MIS")
    assert not is_sample_cost_source("DEMO_SCENARIO")


def _plant_labor_pair(session, *, sample_via: str) -> None:
    session.add(
        PlanVersionRow(
            created_at=datetime(2026, 9, 15, 8, 0, 0),
            trigger="量产隔离",
            snapshot_hash="",
            conflicts_json="[]",
            kit_json="{}",
        )
    )
    session.add(
        SoOrderRow(
            order_no="SO-MASS-1",
            customer="量产客户",
            sales_name="测",
            item_code="P1",
            qty_order="10",
            unit="BOARD",
            due_date=date(2026, 10, 8),
            customer_level=3,
            amount="0",
            is_urgent=False,
            schedule_phase="IN_SCHEDULING",
            order_source="MIS",
        )
    )
    sample_src = "SAMPLE" if sample_via == "source" else "MIS"
    session.add(
        SoOrderRow(
            order_no="SO-SMP-1",
            customer="打样客户",
            sales_name="测",
            item_code="P1",
            qty_order="2",
            unit="BOARD",
            due_date=date(2026, 10, 8),
            customer_level=3,
            amount="0",
            is_urgent=False,
            schedule_phase="IN_SCHEDULING",
            order_source=sample_src,
        )
    )
    if sample_via == "quote":
        session.add(
            CrmQuoteRow(
                code="Q-SMP-1",
                customer_code="C-SMP",
                sample_code="SP-001",
                total_amount="0",
                status="WON",
                order_no="SO-SMP-1",
            )
        )
    session.flush()
    for wo_no, order_no, hours in (
        ("WO-MASS-1", "SO-MASS-1", "24"),
        ("WO-SMP-1", "SO-SMP-1#L1", "10"),
    ):
        session.add(
            WoRow(
                wo_no=wo_no,
                wo_type="FINISHED",
                source_order_no=order_no,
                item_code="P1",
                group_code="MANUAL",
                dept="FINISHED_DEPT",
                qty_order="10",
                qty_board_plan=10,
                due_date=date(2026, 10, 8),
                plan_start=date(2026, 9, 25),
                plan_end=date(2026, 9, 25),
                earliest_start=TODAY,
                crew_plan=3,
                status="RELEASED",
                plan_version=1,
            )
        )
        session.add(
            WoTaskRow(
                wo_no=wo_no,
                dept="FINISHED_DEPT",
                group_code="MANUAL",
                task_date=date(2026, 9, 25),
                qty_board=10,
                hours_wall="8",
                hours_man=hours,
                crew_plan=3,
                seq=1,
                plan_version=1,
            )
        )
    session.commit()


@pytest.fixture
def labor_iso(tmp_path):
    db_path = tmp_path / "sample_labor.db"
    engine = make_engine(db_path)
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, ROOT / "seed" / "seed_data.json")
        session.commit()
        yield factory
    finally:
        session.close()


@pytest.mark.parametrize("sample_via", ["source", "quote"])
def test_sample_hours_excluded_from_mass_product_cost(labor_iso, sample_via):
    session = labor_iso()
    try:
        _plant_labor_pair(session, sample_via=sample_via)
        data = planned_labor_cost_by_product(session, plan_version=1)
    finally:
        session.close()
    p1 = next(p for p in data["products"] if p["item_code"] == "P1")
    assert p1["hours_man_planned"] == 24
    assert p1["order_nos"] == ["SO-MASS-1"]
    assert data["totals"]["hours_man"] == 24
    assert data["sample_excluded"]["hours_man"] == 10
    assert "SO-SMP-1" in data["sample_excluded"]["order_nos"]
    assert "量产" in (data.get("note") or "")
