"""一部产能统计：未报工格空、盒/H 只含直接工时、分品克重、缺克重不进合计。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.prod_stats import dept1_daily, dept1_detail, dept1_efficiency
from db.qty_carryover import confirm_wo_qty
from db.session import init_db, make_engine, session_factory
from db.tables import (
    InvInboundDailyRow,
    MdItemRow,
    MdUomConvertRow,
    PlanVersionRow,
    ProdTimeReportRow,
    SoOrderRow,
    WoRow,
    WoTaskRow,
)

D1 = date(2026, 9, 1)
D2 = date(2026, 9, 2)
HDR = {"X-Demo-Role": "PMC"}


@pytest.fixture
def stats_db(tmp_path):
    engine = make_engine(tmp_path / "dept1_stats.db")
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        _plant_master(session)
        session.commit()
    finally:
        session.close()
    app = create_app(factory)
    with TestClient(app) as client:
        yield client, factory


def _plant_master(session) -> None:
    session.add(
        MdItemRow(
            item_code="P1",
            item_name="手工铲花",
            dept="FINISHED_DEPT",
            group_code="MANUAL",
            unit_sale="BOX",
            pcs_per_board=12,
            board_per_box="4",
            loss_rate="0.05",
            color="黑",
            is_semi=False,
            computable=True,
            prod_category="手工模具",
            kg_per_board="0.25",
            display_uom="BOX",
        )
    )
    session.add(
        MdItemRow(
            item_code="P5",
            item_name="糖花",
            dept="FINISHED_DEPT",
            group_code="MOLD",
            unit_sale="BOX",
            pcs_per_board=16,
            board_per_box="4",
            loss_rate="0.05",
            color="粉",
            is_semi=False,
            computable=True,
            prod_category="糖花",
            kg_per_board="0.08",
            display_uom="BOX",
        )
    )
    session.add(
        MdItemRow(
            item_code="P-NOKG",
            item_name="未维护克重",
            dept="FINISHED_DEPT",
            group_code="MANUAL",
            unit_sale="BOX",
            pcs_per_board=10,
            board_per_box="2",
            loss_rate="0",
            color="-",
            is_semi=False,
            computable=True,
            prod_category="其他",
            kg_per_board=None,
            display_uom="BOX",
        )
    )
    session.add(MdUomConvertRow(item_code="P1", from_uom="BOX", to_uom="BOARD", factor="4"))
    session.add(MdUomConvertRow(item_code="P5", from_uom="BOX", to_uom="BOARD", factor="4"))
    session.add(MdUomConvertRow(item_code="P-NOKG", from_uom="BOX", to_uom="BOARD", factor="2"))
    session.add(
        PlanVersionRow(
            created_at=datetime(2026, 9, 1, 8, 0, 0),
            trigger="统计测试",
            snapshot_hash="",
            conflicts_json="[]",
            kit_json="{}",
        )
    )
    session.flush()


def _add_wo_task(
    session,
    *,
    wo_no: str,
    item_code: str,
    group_code: str,
    task_date: date,
    qty_plan: int,
    qty_actual: int | None = None,
    kg_snap: str | None = None,
) -> None:
    if session.get(SoOrderRow, f"SO-{wo_no}") is None:
        session.add(
            SoOrderRow(
                order_no=f"SO-{wo_no}",
                customer="统计客户",
                sales_name="测",
                item_code=item_code,
                qty_order=str(qty_plan),
                unit="BOARD",
                due_date=date(2026, 10, 1),
                customer_level=3,
                amount="0",
                is_urgent=False,
                schedule_phase="IN_PRODUCTION",
                order_source="TEST",
            )
        )
    if session.get(WoRow, wo_no) is None:
        session.add(
            WoRow(
                wo_no=wo_no,
                wo_type="FINISHED",
                source_order_no=f"SO-{wo_no}",
                item_code=item_code,
                group_code=group_code,
                dept="FINISHED_DEPT",
                qty_order=str(qty_plan),
                qty_board_plan=qty_plan,
                due_date=date(2026, 10, 1),
                plan_start=task_date,
                plan_end=task_date,
                earliest_start=task_date,
                crew_plan=2,
                status="RELEASED",
                plan_version=1,
            )
        )
    session.add(
        WoTaskRow(
            wo_no=wo_no,
            dept="FINISHED_DEPT",
            group_code=group_code,
            task_date=task_date,
            qty_board=qty_plan,
            hours_wall="4",
            hours_man="8",
            crew_plan=2,
            seq=1,
            plan_version=1,
            qty_actual=qty_actual,
            kg_per_board_snap=kg_snap,
        )
    )


def _add_hours(
    session,
    *,
    work_date: date,
    group_code: str,
    hours_actual: str,
    status: str = "CONFIRMED",
    hours_normal: str | None = None,
    hours_ot: str | None = None,
    hours_indirect: str | None = None,
) -> None:
    session.add(
        ProdTimeReportRow(
            work_date=work_date,
            schedule_dept="FINISHED_DEPT",
            group_code=group_code,
            plan_version=1,
            hours_man_planned="8",
            hours_man_actual=hours_actual,
            status=status,
            hours_normal=hours_normal,
            hours_ot=hours_ot,
            hours_indirect_normal=hours_indirect,
        )
    )


def _cell(detail: dict, group: str, category: str, uom: str, day: str) -> dict | None:
    for g in detail["groups"]:
        if g["group_code"] != group:
            continue
        for cat in g["categories"]:
            if cat["category"] != category:
                continue
            for unit in cat["units"]:
                if unit["display_uom"] != uom:
                    continue
                return unit["cells"].get(day)
    return None


def test_unreported_day_actual_is_null(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(session, wo_no="WO-A", item_code="P1", group_code="MANUAL", task_date=D1, qty_plan=40)
        session.commit()
        detail = dept1_detail(session, date_from=D1, date_to=D2)
    finally:
        session.close()
    cell = _cell(detail, "MANUAL", "手工模具", "BOX", "2026-09-01")
    assert cell is not None
    assert cell["qty_plan"] == 10  # 40 版 / 4 → 整数盒
    assert cell["qty_actual"] is None
    assert isinstance(cell["qty_plan"], int)


def test_display_qty_ceils_partial_box(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(session, wo_no="WO-E", item_code="P5", group_code="MOLD", task_date=D1, qty_plan=10)
        session.commit()
        detail = dept1_detail(session, date_from=D1, date_to=D1)
    finally:
        session.close()
    cell = _cell(detail, "MOLD", "糖花", "BOX", "2026-09-01")
    assert cell is not None
    assert cell["qty_plan"] == 3  # 10 版 / 4 = 2.5 → 向上取整



def test_box_per_hour_excludes_indirect(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(
            session,
            wo_no="WO-A",
            item_code="P1",
            group_code="MANUAL",
            task_date=D1,
            qty_plan=40,
            qty_actual=40,
            kg_snap="0.25",
        )
        _add_hours(
            session,
            work_date=D1,
            group_code="MANUAL",
            hours_actual="12",
            hours_normal="8",
            hours_ot="2",
            hours_indirect="4",
        )
        session.commit()
        daily = dept1_daily(session, date_from=D1, date_to=D1)
    finally:
        session.close()
    day = daily["days"]["2026-09-01"]
    assert Decimal(str(day["box_kg"])) == Decimal("10")  # 40 * 0.25
    assert Decimal(str(day["hours_direct"])) == Decimal("10")  # 8+2，不含间接 4
    assert Decimal(str(day["box_per_hour"])) == Decimal("1")
    assert Decimal(str(day["hours_indirect"])) == Decimal("4")


def test_missing_kg_excluded_from_box_equiv(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(
            session,
            wo_no="WO-A",
            item_code="P1",
            group_code="MANUAL",
            task_date=D1,
            qty_plan=40,
            qty_actual=40,
            kg_snap="0.25",
        )
        _add_wo_task(
            session,
            wo_no="WO-B",
            item_code="P-NOKG",
            group_code="MANUAL",
            task_date=D1,
            qty_plan=20,
            qty_actual=20,
        )
        _add_hours(session, work_date=D1, group_code="MANUAL", hours_actual="10")
        session.commit()
        daily = dept1_daily(session, date_from=D1, date_to=D1)
        detail = dept1_detail(session, date_from=D1, date_to=D1)
    finally:
        session.close()
    assert Decimal(str(daily["days"]["2026-09-01"]["box_kg"])) == Decimal("10")
    cell = _cell(detail, "MANUAL", "其他", "BOX", "2026-09-01")
    assert cell is not None
    assert cell["qty_actual"] == 10
    assert cell["box_kg"] is None
    assert cell["missing_kg"] is True


def test_different_item_weights_not_one_to_one(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(
            session,
            wo_no="WO-A",
            item_code="P1",
            group_code="MANUAL",
            task_date=D1,
            qty_plan=40,
            qty_actual=40,
            kg_snap="0.25",
        )
        _add_wo_task(
            session,
            wo_no="WO-C",
            item_code="P5",
            group_code="MOLD",
            task_date=D1,
            qty_plan=40,
            qty_actual=40,
            kg_snap="0.08",
        )
        _add_hours(session, work_date=D1, group_code="MANUAL", hours_actual="5")
        _add_hours(session, work_date=D1, group_code="MOLD", hours_actual="5")
        session.commit()
        daily = dept1_daily(session, date_from=D1, date_to=D1)
    finally:
        session.close()
    # 40*0.25 + 40*0.08 = 13.2，不是 80 盒
    assert Decimal(str(daily["days"]["2026-09-01"]["box_kg"])) == Decimal("13.2")


def test_interval_box_per_hour_skips_empty_days(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(
            session,
            wo_no="WO-A",
            item_code="P1",
            group_code="MANUAL",
            task_date=D1,
            qty_plan=40,
            qty_actual=40,
            kg_snap="0.25",
        )
        _add_wo_task(session, wo_no="WO-D", item_code="P1", group_code="MANUAL", task_date=D2, qty_plan=40)
        _add_hours(session, work_date=D1, group_code="MANUAL", hours_actual="10")
        session.commit()
        eff = dept1_efficiency(session, date_from=D1, date_to=D2)
        daily = dept1_daily(session, date_from=D1, date_to=D2)
    finally:
        session.close()
    assert daily["days"]["2026-09-02"]["box_per_hour"] is None
    assert daily["days"]["2026-09-02"]["box_kg"] is None
    assert Decimal(str(eff["period"]["box_per_hour"])) == Decimal("1")


def test_hours_without_qty_no_box_per_hour(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(session, wo_no="WO-A", item_code="P1", group_code="MANUAL", task_date=D1, qty_plan=40)
        _add_hours(session, work_date=D1, group_code="MANUAL", hours_actual="8")
        session.commit()
        daily = dept1_daily(session, date_from=D1, date_to=D1)
    finally:
        session.close()
    assert daily["days"]["2026-09-01"]["box_per_hour"] is None


def test_confirm_wo_qty_writes_task_qty_actual(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(session, wo_no="WO-A", item_code="P1", group_code="MANUAL", task_date=D1, qty_plan=40)
        session.commit()
        confirm_wo_qty(session, wo_no="WO-A", qty_board_done=32, reported_by="测", work_date=D1)
        session.commit()
        task = session.scalars(select_task(session, "WO-A")).one()
        assert task.qty_actual == 32
        assert Decimal(str(task.kg_per_board_snap)) == Decimal("0.25")
    finally:
        session.close()


def select_task(session, wo_no: str):
    from sqlalchemy import select

    return select(WoTaskRow).where(WoTaskRow.wo_no == wo_no)


def test_inbound_variance(stats_db):
    _client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(
            session,
            wo_no="WO-A",
            item_code="P1",
            group_code="MANUAL",
            task_date=D1,
            qty_plan=40,
            qty_actual=40,
            kg_snap="0.25",
        )
        session.add(
            InvInboundDailyRow(
                work_date=D1,
                schedule_dept="FINISHED_DEPT",
                group_code="MANUAL",
                item_code="P1",
                qty_board=32,
                kg_per_board_snap="0.25",
                source="MOCK",
            )
        )
        session.commit()
        daily = dept1_daily(session, date_from=D1, date_to=D1)
    finally:
        session.close()
    day = daily["days"]["2026-09-01"]
    assert Decimal(str(day["inbound_box_kg"])) == Decimal("8")
    assert Decimal(str(day["variance_box_kg"])) == Decimal("2")


def test_api_dept1_detail_and_forbid_sales(stats_db):
    client, factory = stats_db
    session = factory()
    try:
        _add_wo_task(
            session,
            wo_no="WO-A",
            item_code="P1",
            group_code="MANUAL",
            task_date=D1,
            qty_plan=40,
            qty_actual=40,
            kg_snap="0.25",
        )
        _add_hours(session, work_date=D1, group_code="MANUAL", hours_actual="10")
        session.commit()
    finally:
        session.close()
    ok = client.get("/api/prod-stats/dept1/detail?date_from=2026-09-01&date_to=2026-09-02", headers=HDR)
    assert ok.status_code == 200
    assert ok.json()["data"]["dates"][0] == "2026-09-01"
    denied = client.get(
        "/api/prod-stats/dept1/daily?date_from=2026-09-01&date_to=2026-09-01",
        headers={"X-Demo-Role": "SALES"},
    )
    assert denied.status_code == 403


@pytest.fixture
def seeded_stats_db(tmp_path):
    from db.hr_seed import ensure_hr_seed
    from db.prod_stats_seed import ensure_dept1_stats_seed
    from db.seed import import_seed_json
    from pathlib import Path

    engine = make_engine(tmp_path / "dept1_seed.db")
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, Path(__file__).resolve().parents[1] / "seed" / "seed_data.json")
        ensure_hr_seed(session)
        first = ensure_dept1_stats_seed(session)
        second = ensure_dept1_stats_seed(session)
        session.commit()
    finally:
        session.close()
    yield factory, first, second


def test_dept1_demo_seed_fills_reported_days(seeded_stats_db):
    factory, first, second = seeded_stats_db
    assert first["planted"] is True
    assert first["task_days"] >= 9
    assert second["planted"] is False
    session = factory()
    try:
        daily = dept1_daily(session, date_from=date(2026, 9, 1), date_to=date(2026, 9, 30))
    finally:
        session.close()
    d1 = daily["days"]["2026-09-01"]
    assert d1["box_kg"] is not None and d1["box_kg"] > 1000
    assert d1["hours_direct"] is not None and d1["hours_direct"] > 100
    assert d1["box_per_hour"] is not None
    assert d1["inbound_box_kg"] is not None
    assert d1["variance_box_kg"] is not None
    assert daily["days"]["2026-09-25"]["box_per_hour"] is not None
    assert daily["days"]["2026-09-30"]["box_per_hour"] is None
    assert daily["period"]["box_per_hour"] is not None


def test_dept1_demo_seed_has_multiple_categories(seeded_stats_db):
    factory, _first, _second = seeded_stats_db
    session = factory()
    try:
        detail = dept1_detail(session, date_from=date(2026, 9, 1), date_to=date(2026, 9, 1))
    finally:
        session.close()
    cell_p1 = _cell(detail, "MANUAL", "手工模具", "BOX", "2026-09-01")
    cell_flower = _cell(detail, "MOLD", "糖花", "BOX", "2026-09-01")
    cell_logo = _cell(detail, "POURING", "logo", "BOX", "2026-09-01")
    assert cell_p1 and cell_p1["qty_actual"] is not None
    assert cell_flower and cell_flower["qty_actual"] is not None
    assert cell_logo and cell_logo["qty_actual"] is not None
    assert cell_p1["box_kg"] != cell_flower["box_kg"]
