"""uvicorn 入口：python -m api.app_factory"""

from __future__ import annotations

from db.seed import import_seed_json, needs_seed_reload, reload_seed_json
from db.session import init_db, make_engine, session_factory

from api.main import create_app

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "seed_data.json"
DB = ROOT / "data" / "scheduling.db"

engine = make_engine(DB)
init_db(engine)
factory = session_factory(engine)
from sqlalchemy import func, select

from db.migrate import ensure_schema
from db.tables import MdItemRow

ensure_schema(engine)

session = factory()
try:
    if needs_seed_reload(session, SEED):
        reload_seed_json(session, SEED)
        session.commit()
    else:
        item_count = session.scalar(select(func.count()).select_from(MdItemRow)) or 0
        if item_count == 0:
            import_seed_json(session, SEED)
            session.commit()
except Exception:
    session.rollback()
    raise
finally:
    session.close()

session = factory()
try:
    from db.demo_crm_seed import ensure_demo_crm

    ensure_demo_crm(session)
    session.commit()
except Exception:
    session.rollback()
finally:
    session.close()

app = create_app(factory)
