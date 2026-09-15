"""种子与旧库自动对齐。"""

from pathlib import Path

from db.seed import import_seed_json, needs_seed_reload, reload_seed_json, seed_manifest
from db.session import init_db, make_engine, session_factory
from db.tables import MdItemRow, SoOrderRow
from sqlalchemy import func, select

from tests.conftest import ROOT, SEED_PATH


def test_seed_manifest_nine_orders():
    m = seed_manifest(SEED_PATH)
    assert m["order_count"] == 12
    assert m["item_count"] == 15


def test_needs_reload_when_order_count_stale(tmp_path):
    db = tmp_path / "stale.db"
    engine = make_engine(db)
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, SEED_PATH)
        session.commit()
        assert session.scalar(select(func.count()).select_from(SoOrderRow)) == 12
        session.execute(
            SoOrderRow.__table__.delete().where(SoOrderRow.order_no == "SO-101")
        )
        session.commit()
        assert needs_seed_reload(session, SEED_PATH)
        reload_seed_json(session, SEED_PATH)
        session.commit()
        assert session.scalar(select(func.count()).select_from(SoOrderRow)) == 12
        assert session.scalar(select(func.count()).select_from(MdItemRow)) == 15
    finally:
        session.close()


def test_ensure_seed_backfills_blank_sales_name(tmp_path):
    """旧库订单数为齐但 sales_name 为空时，补种子销售，不整库重导。"""
    from db.seed import ensure_seed_current

    db = tmp_path / "nosales.db"
    engine = make_engine(db)
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, SEED_PATH)
        session.commit()
        row = session.get(SoOrderRow, "SO-004")
        assert row is not None
        row.sales_name = ""
        row.schedule_phase = "IN_SCHEDULING"
        session.commit()

        ensure_seed_current(session, SEED_PATH)
        session.commit()

        again = session.get(SoOrderRow, "SO-004")
        assert again.sales_name == "韩磊"
        assert again.schedule_phase == "IN_SCHEDULING"
        so001 = session.get(SoOrderRow, "SO-001")
        assert so001.sales_name == "陈雨桐"
    finally:
        session.close()
