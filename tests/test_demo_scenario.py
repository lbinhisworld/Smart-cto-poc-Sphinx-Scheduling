"""演示场景台：清场锁、编制、订单集合相交。today 固定 2026-09-15。"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from api.main import create_app
from db.hr_seed import ensure_hr_seed
from db.seed import import_seed_json, needs_seed_reload
from db.session import init_db, make_engine, session_factory
from db.tables import (
    CrmContractRow,
    CrmCustomerRow,
    HrEmployeeRow,
    HrGroupAttendanceRow,
    MdCapacityCalendarRow,
    MdItemRow,
    SoOrderLineRow,
    SoOrderRow,
    StockRow,
    WoRow,
)
from shared.demo_scenario import (
    CORE_SHARE_4,
    DEMO_TODAY,
    SELLABLE_FINISHED,
    SELLABLE_ROUTES,
    DueMode,
    ItemShareMode,
    ScenarioPlanError,
    min_due_for_skus,
    plan_orders,
)

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "seed" / "seed_data.json"

HDR_GM = {"X-Demo-Role": "GM", "Content-Type": "application/json"}
HDR_PMC = {"X-Demo-Role": "PMC", "Content-Type": "application/json"}
HDR_SALES = {"X-Demo-Role": "SALES", "Content-Type": "application/json"}


@pytest.fixture
def iso_db(tmp_path):
    db_path = tmp_path / "scenario.db"
    engine = make_engine(db_path)
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, SEED_PATH)
        ensure_hr_seed(session)
        session.commit()
    finally:
        session.close()
    return factory


@pytest.fixture
def api_client(iso_db):
    app = create_app(iso_db)
    with TestClient(app) as client:
        yield client, iso_db


def test_plan_none_five_orders_disjoint_sets():
    plan = plan_orders(
        order_count=5,
        due_mode=DueMode.FOCUS_FAR,
        item_share=ItemShareMode.NONE,
        today=DEMO_TODAY,
        rng_seed=20260915,
    )
    assert plan["today"] == DEMO_TODAY
    assert len(plan["orders"]) == 5
    sets = [frozenset(o["item_codes"]) for o in plan["orders"]]
    for s in sets:
        assert len(s) == 2
    for i, a in enumerate(sets):
        for b in sets[i + 1 :]:
            assert a & b == set()
    used = set().union(*sets)
    assert used <= set(SELLABLE_FINISHED)
    for o in plan["orders"]:
        assert o["ready_date"] >= DEMO_TODAY
        assert (o["due_date"] - o["ready_date"]).days >= 2
        assert o["schedule_phase"] == "PENDING"


def test_plan_none_ten_orders_rejected():
    with pytest.raises(ScenarioPlanError, match="最多 5"):
        plan_orders(
            order_count=10,
            due_mode=DueMode.UNIFORM,
            item_share=ItemShareMode.NONE,
            today=DEMO_TODAY,
            rng_seed=1,
        )


def test_plan_share_10_1_pair_intersects_one():
    plan = plan_orders(
        order_count=10,
        due_mode=DueMode.UNIFORM,
        item_share=ItemShareMode.SHARE_10_1,
        today=DEMO_TODAY,
        rng_seed=20260915,
    )
    cluster = [o for o in plan["orders"] if o["in_cluster"]]
    assert len(cluster) == 2
    a, b = frozenset(cluster[0]["item_codes"]), frozenset(cluster[1]["item_codes"])
    assert a != b
    assert len(a & b) == 1
    assert plan["core_skus"] == ["P2"]
    assert a & b == {"P2"}
    for o in plan["orders"]:
        if not o["in_cluster"]:
            assert "P2" not in o["item_codes"]


def test_plan_share_20_4_cluster_intersects_four():
    plan = plan_orders(
        order_count=20,
        due_mode=DueMode.FOCUS_MID,
        item_share=ItemShareMode.SHARE_20_4,
        today=DEMO_TODAY,
        rng_seed=20260915,
    )
    cluster = [o for o in plan["orders"] if o["in_cluster"]]
    assert len(cluster) == 4
    core = frozenset(plan["core_skus"])
    assert core == frozenset({"P1", "P2", "P4", "P9"})
    sets = [frozenset(o["item_codes"]) for o in cluster]
    for s in sets:
        assert core <= s
    for i, a in enumerate(sets):
        for b in sets[i + 1 :]:
            assert (a & b) == core
    for o in plan["orders"]:
        if not o["in_cluster"]:
            assert core.isdisjoint(o["item_codes"])


def test_plan_dues_never_before_demo_today():
    """订单交期不得早于 demo-today；含半成品的行还要保证「成品开工−提前期」也不早于 today。"""
    for mode in DueMode:
        shares = (
            [ItemShareMode.NONE, ItemShareMode.SHARE_10_1, ItemShareMode.SHARE_20_4]
            if mode is not DueMode.FOCUS_FAR
            else [ItemShareMode.SHARE_10_1, ItemShareMode.SHARE_20_4]
        )
        # NONE 仅支持最多 5 单；FAR 用 5 单即可覆盖
        for share in shares:
            n = 5
            plan = plan_orders(n, mode, share, DEMO_TODAY, 20260915)
            for o in plan["orders"]:
                assert o["due_date"] >= DEMO_TODAY, (mode, share, o)
                assert o["due_date"] >= min_due_for_skus(o["item_codes"], DEMO_TODAY)
                assert o["due_date"].isoweekday() <= 5
                assert o["ready_date"] >= DEMO_TODAY
                assert (o["due_date"] - o["ready_date"]).days >= 2
                for code in o["item_codes"]:
                    hint = SELLABLE_ROUTES[code]
                    if hint.needs_semi:
                        implied_semi = o["due_date"] - timedelta(days=hint.lead_time_days)
                        assert implied_semi >= DEMO_TODAY, (o["order_no"], code, implied_semi)


def test_plan_due_fence_within_plus_four():
    plan = plan_orders(
        order_count=5,
        due_mode=DueMode.FOCUS_FENCE,
        item_share=ItemShareMode.SHARE_10_1,
        today=DEMO_TODAY,
        rng_seed=7,
    )
    hi = DEMO_TODAY + timedelta(days=4)
    lo = DEMO_TODAY + timedelta(days=2)
    for o in plan["orders"]:
        assert o["due_date"] >= DEMO_TODAY
        assert o["due_date"].isoweekday() <= 5
        needs_semi = any(SELLABLE_ROUTES[c].needs_semi for c in o["item_codes"])
        if needs_semi:
            assert o["due_date"] >= DEMO_TODAY + timedelta(days=4)
        else:
            assert lo <= o["due_date"] <= hi


def test_plan_same_seed_reproducible():
    a = plan_orders(5, DueMode.UNIFORM, ItemShareMode.SHARE_10_1, DEMO_TODAY, 42)
    b = plan_orders(5, DueMode.UNIFORM, ItemShareMode.SHARE_10_1, DEMO_TODAY, 42)
    assert [o["item_codes"] for o in a["orders"]] == [o["item_codes"] for o in b["orders"]]
    assert [o["due_date"] for o in a["orders"]] == [o["due_date"] for o in b["orders"]]
    assert [o["ready_date"] for o in a["orders"]] == [o["ready_date"] for o in b["orders"]]


def test_reset_clears_orders_keeps_items_and_locks(iso_db):
    from db.demo_scenario import reset_order_scenario

    session = iso_db()
    try:
        session.add(
            WoRow(
                wo_no="WO-TMP",
                wo_type="FINISHED",
                source_order_no="SO-001",
                item_code="P1",
                group_code="MANUAL",
                dept="FINISHED_DEPT",
                qty_order="10",
                qty_board_plan=10,
                due_date=DEMO_TODAY,
                earliest_start=DEMO_TODAY,
                crew_plan=3,
                status="PLANNED",
                plan_version=1,
            )
        )
        session.commit()
        items_before = session.scalar(select(func.count()).select_from(MdItemRow))
        s2 = session.get(StockRow, "S2")
        assert s2 is not None and float(s2.qty_available) > 0

        stats = reset_order_scenario(session)
        session.commit()

        assert stats["orders"] == 0
        assert session.scalar(select(func.count()).select_from(SoOrderRow)) == 0
        assert session.scalar(select(func.count()).select_from(WoRow)) == 0
        assert session.scalar(select(func.count()).select_from(MdItemRow)) == items_before
        assert float(session.get(StockRow, "S2").qty_available) == 0
        assert needs_seed_reload(session, SEED_PATH) is False
    finally:
        session.close()


def test_apply_roster_five_per_group(iso_db):
    from db.demo_scenario import apply_roster

    session = iso_db()
    try:
        staff_before = session.scalars(
            select(HrEmployeeRow).where(HrEmployeeRow.employee_kind == "STAFF")
        ).all()
        staff_nos = {e.emp_no for e in staff_before}
        out = apply_roster(session, headcount=5)
        session.commit()
        assert out["groups"] == 6
        assert out["employees"] == 30
        wang = session.get(HrEmployeeRow, "E2001")
        assert wang is not None
        assert wang.name == "王强"
        assert wang.is_team_leader
        for dept, group in (
            ("FINISHED_DEPT", "MANUAL"),
            ("FINISHED_DEPT", "MOLD"),
            ("FINISHED_DEPT", "POURING"),
            ("SEMI_DEPT", "MANUAL"),
            ("SEMI_DEPT", "MOLD"),
            ("SEMI_DEPT", "POURING"),
        ):
            n = session.scalar(
                select(func.count()).select_from(HrEmployeeRow).where(
                    HrEmployeeRow.schedule_dept == dept,
                    HrEmployeeRow.group_code == group,
                    HrEmployeeRow.status == "ACTIVE",
                )
            )
            assert n == 5
            cal_n = session.scalar(
                select(func.count()).select_from(MdCapacityCalendarRow).where(
                    MdCapacityCalendarRow.dept == dept,
                    MdCapacityCalendarRow.group_code == group,
                    MdCapacityCalendarRow.is_workday.is_(True),
                    MdCapacityCalendarRow.headcount != 5,
                )
            )
            assert cal_n == 0
            att = session.scalar(
                select(func.count()).select_from(HrGroupAttendanceRow).where(
                    HrGroupAttendanceRow.schedule_dept == dept,
                    HrGroupAttendanceRow.group_code == group,
                    HrGroupAttendanceRow.headcount_present == 5,
                )
            )
            assert att >= 1
        staff_after = {e.emp_no for e in session.scalars(
            select(HrEmployeeRow).where(HrEmployeeRow.employee_kind == "STAFF")
        ).all()}
        assert staff_nos <= staff_after
    finally:
        session.close()


def test_share_20_4_explodes_core_skus_into_finished_wos(iso_db):
    from db.demo_scenario import generate_orders
    from db.order_lifecycle import add_to_scheduling_pool
    from db.snapshot import load_schedule_input
    from engine.models import WoType
    from engine.schedule import schedule

    session = iso_db()
    try:
        generate_orders(
            session,
            order_count=5,
            due_mode="FOCUS_FAR",
            item_share="SHARE_20_4",
        )
        add_to_scheduling_pool(session, [f"SO-S00{i}" for i in range(1, 6)])
        session.commit()
        inp = load_schedule_input(session, today=DEMO_TODAY)
        exploded = [o.order_no for o in inp.orders if "#L" in o.order_no]
        assert exploded, "场景单必须按行展开"
        result = schedule(inp)
        finished = [w for w in result.wos if w.wo_type == WoType.FINISHED]
        items = {w.item_code for w in finished}
        assert set(CORE_SHARE_4) <= items
        s001 = [w for w in finished if w.source_order_no.startswith("SO-S001")]
        assert len(s001) >= 4
        kinds = [e.kind for e in (result.trace.events if result.trace else [])]
        assert "expand_lines" in kinds
        assert "sku_intersect" in kinds
    finally:
        session.close()


def test_generate_api_pending_and_contracts(api_client):
    client, factory = api_client
    prev = client.post(
        "/api/demo/scenario/preview-orders",
        headers=HDR_GM,
        json={
            "order_count": 5,
            "due_mode": "FOCUS_FAR",
            "item_share": "SHARE_10_1",
            "rng_seed": 20260915,
        },
    )
    assert prev.status_code == 200, prev.text
    assert prev.json()["data"]["order_count"] == 5

    r = client.post(
        "/api/demo/scenario/generate-orders",
        headers=HDR_GM,
        json={
            "order_count": 5,
            "due_mode": "FOCUS_FAR",
            "item_share": "SHARE_10_1",
            "rng_seed": 20260915,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["order_count"] == 5
    assert data["locked"] is True

    session = factory()
    try:
        orders = list(session.scalars(select(SoOrderRow)).all())
        assert len(orders) == 5
        assert all(o.schedule_phase == "PENDING" for o in orders)
        assert all(o.order_source == "DEMO_SCENARIO" for o in orders)
        assert all((o.customer_code or "").startswith("SCEN-") for o in orders)
        assert all((o.contract_no or "").startswith("HT-SCEN-") for o in orders)
        for o in orders:
            assert o.due_date >= DEMO_TODAY
            lines = list(
                session.scalars(select(SoOrderLineRow).where(SoOrderLineRow.order_no == o.order_no))
            )
            assert len(lines) >= 2
            contract = session.get(CrmContractRow, o.contract_no)
            assert contract is not None and contract.status == "ACTIVE"
            cust = session.get(CrmCustomerRow, o.customer_code)
            assert cust is not None
            assert (o.sales_name or "").strip()
            assert o.sales_name == cust.owner_sales
        assert needs_seed_reload(session, SEED_PATH) is False
    finally:
        session.close()


def test_generate_then_mis_orders_list(api_client):
    """清场后列表仍会 ensure_demo_crm，不能再为已删除的 SO-003 补变更单。"""
    client, _ = api_client
    gen = client.post(
        "/api/demo/scenario/generate-orders",
        headers=HDR_GM,
        json={"order_count": 5, "due_mode": "UNIFORM", "item_share": "SHARE_10_1"},
    )
    assert gen.status_code == 200, gen.text
    r = client.get("/api/mis/orders?view=all", headers=HDR_GM)
    assert r.status_code == 200, r.text
    rows = r.json()["data"]["rows"]
    assert len(rows) == 5
    assert {x["order_no"] for x in rows} == {f"SO-S00{i}" for i in range(1, 6)}
    assert all(x["schedule_phase"] == "PENDING" for x in rows)
    assert all(x["due_date"] >= DEMO_TODAY.isoformat() for x in rows)


def test_generate_none_ten_rejected(api_client):
    client, _ = api_client
    r = client.post(
        "/api/demo/scenario/preview-orders",
        headers=HDR_GM,
        json={"order_count": 10, "due_mode": "UNIFORM", "item_share": "NONE"},
    )
    assert r.status_code == 400


def test_scenario_write_forbidden_for_sales(api_client):
    client, _ = api_client
    r = client.post("/api/demo/scenario/reset-orders", headers=HDR_SALES)
    assert r.status_code == 403


def test_restore_seed_returns_twelve(api_client):
    client, _ = api_client
    client.post(
        "/api/demo/scenario/generate-orders",
        headers=HDR_GM,
        json={"order_count": 5, "due_mode": "UNIFORM", "item_share": "SHARE_10_1"},
    )
    r = client.post("/api/demo/scenario/restore-seed", headers=HDR_GM)
    assert r.status_code == 200, r.text
    mis = client.get("/api/mis/orders?view=all", headers=HDR_GM)
    assert mis.status_code == 200, mis.text
    rows = mis.json()["data"]["rows"]
    assert len(rows) == 12
    assert all(not r["order_no"].startswith("SO-D1S-") for r in rows)
    assert all(r["line_count"] == 1 for r in rows)
    assert mis.json()["data"]["stats"]["total"] == 12
    orders = client.get("/api/orders").json()["data"]["orders"]
    assert len(orders) == 12
    phases = [o["schedule_phase"] for o in orders]
    assert phases.count("IN_SCHEDULING") == 3
