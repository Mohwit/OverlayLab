from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Iterator

from contextlib import contextmanager

from app.core.config import settings

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS base_files (
    path        TEXT PRIMARY KEY,
    content     BLOB,
    is_dir      INTEGER NOT NULL DEFAULT 0,
    size        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    name            TEXT,
    root_node_id    TEXT NOT NULL,
    active_node_id  TEXT NOT NULL,
    color           TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    node_id         TEXT PRIMARY KEY,
    parent_node_id  TEXT,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id),
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS node_files (
    node_id     TEXT NOT NULL REFERENCES nodes(node_id),
    path        TEXT NOT NULL,
    content     BLOB,
    is_dir      INTEGER NOT NULL DEFAULT 0,
    size        INTEGER NOT NULL DEFAULT 0,
    whiteout    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (node_id, path)
);
"""


class Database:
    """Thread-safe SQLite connection manager for recall.db.

    Each thread gets its own connection via thread-local storage.
    WAL journal mode is enabled for concurrent read performance.
    """

    def __init__(self, db_path: Path | str | None = None):
        if db_path is None:
            db_path = settings.overlay_root / "recall.db"
        self._db_path = Path(db_path)
        self._local = threading.local()

    @property
    def path(self) -> Path:
        return self._db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def init_schema(self) -> None:
        """Create tables if they don't already exist."""
        conn = self._get_connection()
        conn.executescript(_SCHEMA_SQL)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection with an implicit transaction.

        Commits on clean exit, rolls back on exception.
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    def reset(self) -> None:
        """Drop all data (used by admin reset). Preserves schema."""
        with self.connect() as conn:
            conn.execute("DELETE FROM node_files")
            conn.execute("DELETE FROM nodes")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM base_files")

    def close(self) -> None:
        """Close the current thread's connection if open."""
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
