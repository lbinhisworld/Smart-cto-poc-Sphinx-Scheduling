from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.base import Base


def make_engine(db_path: Path | str = "data/scheduling.db"):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})


def init_db(engine) -> None:
    from db.migrate import ensure_schema

    ensure_schema(engine)


def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def session_scope(factory) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
