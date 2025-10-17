"""Database dependency for FastAPI routes."""
from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from prooforigin.core.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["get_db"]
