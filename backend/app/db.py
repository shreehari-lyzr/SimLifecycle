"""SQLAlchemy engine, session factory, and FastAPI dependency.

SQLite is used for a zero-setup, self-contained prototype. The ``Base`` and
session plumbing are intentionally generic so the backend can be pointed at
Postgres later by changing only ``settings.database_url``.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# check_same_thread=False is required because the APScheduler background job and
# the request handlers run on different threads but share the SQLite file.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Import models so they are registered on Base.metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
