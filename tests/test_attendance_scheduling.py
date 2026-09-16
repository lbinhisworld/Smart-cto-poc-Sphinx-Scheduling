"""出勤同步 → 排程日历 headcount_present。"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from db.attendance_capacity import sync_attendance_from_punches
from db.hr_seed import ensure_hr_seed
from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory
from db.snapshot import load_schedule_input
from engine.models import Dept, GroupCode
from tests.conftest import ROOT, TODAY


@pytest.fixture
def hr_client(tmp_path):
    db_path = tmp_path / "att.db"
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


HDR = {"X-Demo-Role": "HR"}


def test_sync_attendance_feeds_schedule_input(hr_client):
    client, factory = hr_client
    session = factory()
    try:
        ensure_hr_seed(session)
        session.commit()
        sync_attendance_from_punches(session, date(2026, 9, 15))
        session.commit()
        inp = load_schedule_input(session, today=TODAY, order_nos=["SO-001"])
        manual = next(
            c
            for c in inp.calendar
            if c.dept == Dept.FINISHED_DEPT
            and c.group_code == GroupCode.MANUAL
            and c.work_date == date(2026, 9, 15)
        )
        assert manual.headcount_present is not None
        assert manual.headcount_present >= 1
    finally:
        session.close()

    resp = client.post(
        "/api/hr/attendance/sync-to-scheduling",
        params={"work_date": "2026-09-15"},
        headers=HDR,
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_manual_attendance_api(hr_client):
    client, _ = hr_client
    resp = client.post(
        "/api/hr/attendance/manual",
        headers=HDR,
        json={
            "schedule_dept": "FINISHED_DEPT",
            "group_code": "MOLD",
            "work_date": "2026-10-01",
            "headcount_present": 1,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["headcount_present"] == 1
