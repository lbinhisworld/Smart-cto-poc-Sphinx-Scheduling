"""演示线第 1 步人员列表落 hr_employee。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from db.guided_demo_runs import create_run, seed_step, start_run
from db.tables import HrEmployeeRow

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "scheduling_test_guided_roster_apply.db"


@pytest.fixture()
def db_session():
    from db.demo_manual_data import set_manual_data_mode
    from db.migrate import ensure_schema
    from db.session import init_db, make_engine, session_factory

    if DB.is_file():
        DB.unlink()
    engine = make_engine(DB)
    init_db(engine)
    ensure_schema(engine)
    factory = session_factory(engine)
    session = factory()
    set_manual_data_mode(session, True)
    session.commit()
    yield session
    session.close()
    if DB.is_file():
        DB.unlink()


def test_roster_seed_creates_employees(db_session):
    run = create_run(db_session, title="", role="GM")
    start_run(db_session, run["id"], role="GM")
    db_session.commit()
    out = seed_step(db_session, run["id"], "roster", role="GM")
    db_session.commit()

    assert out["apply"]["applied"] is True
    assert out["apply"]["employees_created"] == 5
    n = int(db_session.scalar(select(func.count()).select_from(HrEmployeeRow)) or 0)
    assert n == 5
    nos = list(db_session.scalars(select(HrEmployeeRow.emp_no)).all())
    assert all(no.startswith("GD-") for no in nos)
    assert all("-E" in no for no in nos)
