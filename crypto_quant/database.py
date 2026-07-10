from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import load_runtime_settings
from .db_models import Base


def engine_from_url(database_url: str | None = None) -> Engine:
    runtime = load_runtime_settings()
    url = database_url or runtime.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


def init_db(engine: Engine | None = None) -> None:
    target = engine or engine_from_url()
    Base.metadata.create_all(target)


def session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    target = engine or engine_from_url()
    return sessionmaker(bind=target, autoflush=False, autocommit=False, future=True)


def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    factory = session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def database_online(engine: Engine | None = None) -> bool:
    try:
        target = engine or engine_from_url()
        with target.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
