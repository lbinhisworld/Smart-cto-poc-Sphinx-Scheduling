"""演示线第 2 步产品列表落 md_item / BOM。"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from db.guided_demo_runs import create_run, seed_step, start_run
from db.guided_demo_step_apply import _story_root_item_codes
from db.tables import MdItemRow

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "scheduling_test_guided_product_apply.db"


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


def test_product_seed_after_roster(db_session):
    run = create_run(db_session, title="", role="GM")
    run_id = run["id"]
    start_run(db_session, run_id, role="GM")
    db_session.commit()
    seed_step(db_session, run_id, "roster", role="GM")
    db_session.commit()
    out = seed_step(db_session, run_id, "product", role="GM")
    db_session.commit()

    assert out["apply"]["applied"] is True
    roots = _story_root_item_codes()
    n = int(
        db_session.scalar(select(func.count()).select_from(MdItemRow).where(MdItemRow.item_code.in_(roots)))
        or 0
    )
    assert n == len(roots)
