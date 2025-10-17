"""SQLite helpers used by ProofOrigin."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

SCHEMA_STATEMENTS: Iterable[str] = (
    """
    CREATE TABLE IF NOT EXISTS proofs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hash TEXT UNIQUE,
        filename TEXT,
        signature TEXT,
        public_key TEXT,
        timestamp REAL,
        phash TEXT,
        dhash TEXT,
        semantic_hash TEXT,
        content_type TEXT,
        file_size INTEGER,
        metadata TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS anchors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE,
        merkle_root TEXT,
        proof_count INTEGER,
        transaction_hash TEXT,
        timestamp REAL,
        anchor_signature TEXT,
        created_at REAL DEFAULT (strftime('%s', 'now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS similarities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proof_id INTEGER,
        similar_proof_id INTEGER,
        similarity_score REAL,
        match_type TEXT,
        confidence TEXT,
        created_at REAL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (proof_id) REFERENCES proofs (id),
        FOREIGN KEY (similar_proof_id) REFERENCES proofs (id)
    )
    """,
)


def connect(database_path: str) -> sqlite3.Connection:
    """Return a connection to the SQLite database with row factory enabled."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add ``column`` to ``table`` when it is missing."""
    cursor = connection.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db(database_path: str) -> None:
    """Initialize the SQLite database if required."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with connect(database_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)

        ensure_column(connection, "anchors", "anchor_signature", "TEXT")

        connection.commit()


__all__ = ["connect", "init_db"]
