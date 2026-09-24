"""销售目标 · 年 / 月 / 周。"""

from datetime import date

from fastapi.testclient import TestClient

from api.app_factory import app
from db.crm_goal_period import (
    PERIOD_PACK_KEY,
    delete_year_goal,
    ensure_demo_goal_period,
    mobile_goal_blocks,
    split_int,
    week_index,
    week_key,
)
from db.session import make_engine, session_factory
from db.tables import AppSettingRow

client = TestClient(app)
MGR = {"X-Demo-Role": "SALES_MGR"}


def _force_goal_seed(session):
    row = session.get(AppSettingRow, PERIOD_PACK_KEY)
    if row is not None:
        session.delete(row)
    delete_year_goal(session, owner="李业务", year=2026)
    session.flush()


def test_week_index_demo_day():
    assert week_index(15) == 3
    assert week_key(2026, 9, 3) == "2026-09-W3"


def test_split_int_sums():
    parts = split_int(10, 12)
    assert len(parts) == 12
    assert sum(parts) == 10


def test_demo_week_visit_gap():
    engine = make_engine(__import__("pathlib").Path("data/scheduling.db"))
    factory = session_factory(engine)
    session = factory()
    try:
        _force_goal_seed(session)
        ensure_demo_goal_period(session)
        session.commit()
        blocks = mobile_goal_blocks(session, "李业务", date(2026, 9, 15))
        visit = next(row for row in blocks["week"]["lines"] if row["metric"] == "拜访量")
        assert visit["target"] > 0
        assert visit["gap"] > 0
    finally:
        session.close()


def test_amount_metrics_are_decimal_strings_in_payload():
    engine = make_engine(__import__("pathlib").Path("data/scheduling.db"))
    factory = session_factory(engine)
    session = factory()
    try:
        _force_goal_seed(session)
        ensure_demo_goal_period(session)
        session.commit()
        blocks = mobile_goal_blocks(session, "李业务", date(2026, 9, 15))
        signed = next(row for row in blocks["year"]["lines"] if row["metric"] == "签约金额")
        assert signed.get("is_amount")
        assert isinstance(signed["display_target"], str)
    finally:
        session.close()


def test_save_year_and_split_api():
    res = client.post(
        "/api/crm/goals/year",
        headers=MGR,
        json={
            "owner_sales": "李业务",
            "owner_dept": "销售部",
            "year": 2026,
            "targets": {"新增客户数": 48, "拜访量": 144, "签约金额": "360000.00", "回款金额": "240000.00"},
            "auto_split": True,
        },
    )
    assert res.status_code == 200, res.text
    tree = client.get("/api/crm/goals/periods?year=2026&owner_sales=李业务", headers=MGR).json()["data"]
    assert tree[0]["months"][0]["weeks"]


def test_goal_periods_api():
    res = client.get("/api/crm/goals/periods?year=2026", headers=MGR)
    assert res.status_code == 200, res.text
    rows = res.json()["data"]
    assert any(row["owner_sales"] == "李业务" for row in rows)
    assert rows[0]["months"]
