"""Phase 5：派工单 Excel 导出。"""

from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from openpyxl import load_workbook

from db.dispatch_export import build_dispatch_workbook_bytes
from db.repositories import run_schedule
from db.session import session_factory
from db.seed import import_seed_json, needs_seed_reload, reload_seed_json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "seed_data.json"
DB = ROOT / "data" / "scheduling_test_export.db"


@pytest.fixture()
def db_session():
    from db.session import init_db, make_engine

    if DB.is_file():
        DB.unlink()
    engine = make_engine(DB)
    init_db(engine)
    from db.migrate import ensure_schema

    ensure_schema(engine)
    factory = session_factory(engine)
    session = factory()
    if needs_seed_reload(session, SEED):
        reload_seed_json(session, SEED)
    else:
        import_seed_json(session, SEED)
    session.commit()
    yield session
    session.close()
    if DB.is_file():
        DB.unlink()


def test_dispatch_export_has_task_rows(db_session):
    run_schedule(
        db_session,
        today=date(2026, 9, 15),
        order_nos=["SO-001", "SO-002", "SO-003"],
        persist=True,
        trigger="export-test",
    )
    db_session.commit()
    raw = build_dispatch_workbook_bytes(db_session)
    wb = load_workbook(BytesIO(raw))
    assert "派工单" in wb.sheetnames
    ws = wb["派工单"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    assert len(rows) >= 3
    assert any(r[0] for r in rows)
