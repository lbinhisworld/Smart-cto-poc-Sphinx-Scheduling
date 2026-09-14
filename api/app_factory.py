"""uvicorn 入口：python -m api.app_factory"""

from __future__ import annotations

from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory

from api.main import create_app

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "seed_data.json"
DB = ROOT / "data" / "scheduling.db"

engine = make_engine(DB)
init_db(engine)
factory = session_factory(engine)
from sqlalchemy import func, select

from db.tables import SoOrderRow

session = factory()
try:
    count = session.scalar(select(func.count()).select_from(SoOrderRow)) or 0
    if count == 0:
        import_seed_json(session, SEED)
        session.commit()
except Exception:
    session.rollback()
finally:
    session.close()

app = create_app(factory)
