"""演示线 · 重置系统（全库清空 + 禁止自动灌种子）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from db.demo_crm_seed import ensure_demo_crm
from db.demo_manual_data import is_manual_data_mode
from db.demo_system_reset import reset_demo_system
from db.guided_demo_runs import create_run, list_runs, start_run
from db.hr_seed import ensure_hr_seed
from db.seed import ensure_seed_current
from db.tables import CrmQuoteRow, DemoRunRow, MdItemRow, SoOrderRow

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "scheduling_test_system_reset.db"
SEED_PATH = ROOT / "seed" / "seed_data.json"


@pytest.fixture()
def db_session():
    from db.migrate import ensure_schema
    from db.session import init_db, make_engine, session_factory

    if DB.is_file():
        DB.unlink()
    engine = make_engine(DB)
    init_db(engine)
    ensure_schema(engine)
    factory = session_factory(engine)
    session = factory()
    yield session
    session.close()
    if DB.is_file():
        DB.unlink()


def test_reset_system_empty_and_blocks_auto_seed(db_session):
    run = create_run(db_session, title="将被清掉", role="GM")
    start_run(db_session, run["id"], role="GM")
    db_session.commit()

    stats = reset_demo_system(db_session)
    db_session.commit()

    assert stats["manual_data_mode"] is True
    assert is_manual_data_mode(db_session)
    assert list_runs(db_session) == []
    assert db_session.scalar(select(func.count()).select_from(DemoRunRow)) == 0
    assert db_session.scalar(select(func.count()).select_from(MdItemRow)) == 0
    assert db_session.scalar(select(func.count()).select_from(SoOrderRow)) == 0
    assert db_session.scalar(select(func.count()).select_from(CrmQuoteRow)) == 0

    ensure_demo_crm(db_session)
    ensure_hr_seed(db_session)
    ensure_seed_current(db_session, SEED_PATH)
    db_session.commit()

    assert db_session.scalar(select(func.count()).select_from(CrmQuoteRow)) == 0
    assert db_session.scalar(select(func.count()).select_from(MdItemRow)) == 0
