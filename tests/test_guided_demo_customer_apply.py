"""演示线第 3 步客户列表落 crm_customer。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from db.guided_demo_runs import create_run, seed_step, start_run
from db.tables import CrmCustomerRow

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "scheduling_test_guided_customer_apply.db"


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


def test_customer_seed_after_product(db_session):
    run = create_run(db_session, title="", role="GM")
    run_id = run["id"]
    start_run(db_session, run_id, role="GM")
    db_session.commit()
    seed_step(db_session, run_id, "roster", role="GM")
    seed_step(db_session, run_id, "product", role="GM")
    db_session.commit()
    out = seed_step(db_session, run_id, "customer", role="GM")
    db_session.commit()

    assert out["apply"]["applied"] is True
    assert out["apply"]["customers_created"] == 5
    n = int(db_session.scalar(select(func.count()).select_from(CrmCustomerRow)) or 0)
    assert n == 5
    codes = list(db_session.scalars(select(CrmCustomerRow.code)).all())
    assert all(c.startswith("GD-") and "-C" in c for c in codes)

    from datetime import date

    from db.crm_customer_portal import list_mine

    mine = list_mine(db_session, role="SALES", actor="李业务", today=date(2026, 9, 15))
    assert len(mine["items"]) == 5
