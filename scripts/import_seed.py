#!/usr/bin/env python3
"""导入 seed/seed_data.json → data/scheduling.db"""

from __future__ import annotations

from pathlib import Path

from db.seed import import_seed_json
from db.session import init_db, make_engine, session_factory

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "seed_data.json"
DB = ROOT / "data" / "scheduling.db"


def main() -> None:
    engine = make_engine(DB)
    init_db(engine)
    factory = session_factory(engine)
    session = factory()
    try:
        import_seed_json(session, SEED)
        session.commit()
        print(f"Imported {SEED} -> {DB}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
