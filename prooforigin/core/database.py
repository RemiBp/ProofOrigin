"""Database session and base model configuration."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import get_settings


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""


settings = get_settings()

connect_args = {"check_same_thread": False} if settings.resolved_database_url.startswith("sqlite") else {}

_engine = create_engine(
    settings.resolved_database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_database() -> None:
    """Create database tables for the current metadata."""
    import prooforigin.core.models  # noqa: F401 ensures models are registered

    Base.metadata.create_all(bind=_engine)


def get_engine():
    return _engine


@contextmanager
def session_scope() -> Generator:
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:  # pragma: no cover - defensive rollback
        session.rollback()
        raise
    finally:
        session.close()


__all__ = ["Base", "SessionLocal", "init_database", "session_scope", "get_engine"]
