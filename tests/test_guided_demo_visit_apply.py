"""演示线第 4 步拜访签到落 crm_field_visit。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from db.crm_field_visit import list_field_visits
from db.guided_demo_runs import create_run, seed_step, start_run
from db.tables import CrmFieldVisitRow

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "scheduling_test_guided_visit_apply.db"


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


def test_visit_stranger_seed_after_customer(db_session):
    run = create_run(db_session, title="", role="GM")
    run_id = run["id"]
    start_run(db_session, run_id, role="GM")
    db_session.commit()
    for sid in ("roster", "product", "customer"):
        seed_step(db_session, run_id, sid, role="GM")
        db_session.commit()
    out = seed_step(db_session, run_id, "visit_stranger", role="GM")
    db_session.commit()

    assert out["apply"]["applied"] is True
    assert out["apply"]["visits_created"] == 5
    n = int(db_session.scalar(select(func.count()).select_from(CrmFieldVisitRow)) or 0)
    assert n == 5
    codes = list(db_session.scalars(select(CrmFieldVisitRow.code)).all())
    assert all(c.startswith("GD-") and "-V" in c for c in codes)

    rows = list_field_visits(db_session, role="SALES", actor="李业务")
    assert len(rows) == 5
    assert all(r.get("customer_code") for r in rows)
