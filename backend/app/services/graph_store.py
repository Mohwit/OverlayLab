from __future__ import annotations

import threading
import uuid

from app.core.models import NodeRecord, SessionRecord, now_utc
from app.services.db import Database

SESSION_COLORS = [
    "#0f766e",
    "#1d4ed8",
    "#b45309",
    "#be123c",
    "#4338ca",
    "#0f766e",
    "#166534",
    "#a16207",
]


class GraphStore:
    """Manages sessions and nodes backed by a SQLite database.

    Replaces the previous JSON-file + in-memory graph persistence with
    direct reads/writes against the ``sessions`` and ``nodes`` tables.
    Directory creation, lowerdir expansion, and JSON serialisation are
    no longer needed -- ancestry is tracked implicitly via each node's
    ``parent_node_id`` column.
    """

    def __init__(self, db: Database):
        self._db = db
        self._lock = threading.RLock()

    def load(self) -> None:
        """No-op retained for startup compatibility.

        The SQLite schema is initialised by ``Database.init_schema()``
        before the application starts; there is nothing extra to load.
        """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def _session_color(self, conn) -> str:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM sessions").fetchone()
        count = row["cnt"] if row else 0
        return SESSION_COLORS[count % len(SESSION_COLORS)]

    @staticmethod
    def _session_from_row(row) -> SessionRecord:
        return SessionRecord(
            session_id=row["session_id"],
            name=row["name"],
            root_node_id=row["root_node_id"],
            active_node_id=row["active_node_id"],
            color=row["color"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _node_from_row(row) -> NodeRecord:
        return NodeRecord(
            node_id=row["node_id"],
            parent_node_id=row["parent_node_id"],
            session_id=row["session_id"],
            created_at=row["created_at"],
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create_session(
        self, name: str | None = None, from_node_id: str | None = None
    ) -> tuple[SessionRecord, NodeRecord]:
        with self._lock:
            session_id = self._new_id("sess")
            node_id = self._new_id("node")
            now = now_utc()

            with self._db.connect() as conn:
                color = self._session_color(conn)

                conn.execute(
                    "INSERT INTO sessions "
                    "(session_id, name, root_node_id, active_node_id, color, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, name, node_id, node_id, color, now),
                )
                conn.execute(
                    "INSERT INTO nodes "
                    "(node_id, parent_node_id, session_id, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (node_id, from_node_id, session_id, now),
                )

            session = SessionRecord(
                session_id=session_id,
                name=name,
                root_node_id=node_id,
                active_node_id=node_id,
                color=color,
                created_at=now,
            )
            node = NodeRecord(
                node_id=node_id,
                parent_node_id=from_node_id,
                session_id=session_id,
                created_at=now,
            )
            return session, node

    def create_node(self, session_id: str, from_node_id: str) -> NodeRecord:
        with self._lock:
            node_id = self._new_id("node")
            now = now_utc()

            with self._db.connect() as conn:
                conn.execute(
                    "INSERT INTO nodes "
                    "(node_id, parent_node_id, session_id, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (node_id, from_node_id, session_id, now),
                )
                conn.execute(
                    "UPDATE sessions SET active_node_id = ? WHERE session_id = ?",
                    (node_id, session_id),
                )

            return NodeRecord(
                node_id=node_id,
                parent_node_id=from_node_id,
                session_id=session_id,
                created_at=now,
            )

    def set_active_node(self, session_id: str, node_id: str) -> None:
        with self._lock:
            with self._db.connect() as conn:
                conn.execute(
                    "UPDATE sessions SET active_node_id = ? WHERE session_id = ?",
                    (node_id, session_id),
                )

    def update_node(self, node: NodeRecord) -> None:
        """No-op retained for backward compatibility.

        Node rows are immutable after creation in the SQLite schema
        (overlay path fields and mount_state no longer exist).  Callers
        that still invoke this will be cleaned up when the routes are
        migrated.
        """

    def reset_graph(self) -> dict[str, int]:
        with self._lock:
            with self._db.connect() as conn:
                node_count = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM nodes"
                ).fetchone()["cnt"]
                session_count = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM sessions"
                ).fetchone()["cnt"]
                conn.execute("DELETE FROM node_files")
                conn.execute("DELETE FROM nodes")
                conn.execute("DELETE FROM sessions")
                conn.execute("DELETE FROM base_files")
            return {"nodes": node_count, "sessions": session_count}

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT session_id, name, root_node_id, active_node_id, color, created_at "
                "FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return self._session_from_row(row)

    def get_node(self, node_id: str) -> NodeRecord | None:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT node_id, parent_node_id, session_id, created_at "
                "FROM nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()
        if row is None:
            return None
        return self._node_from_row(row)

    def get_all_sessions(self) -> list[SessionRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT session_id, name, root_node_id, active_node_id, color, created_at "
                "FROM sessions ORDER BY created_at"
            ).fetchall()
        return [self._session_from_row(r) for r in rows]

    def get_all_nodes(self) -> list[NodeRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT node_id, parent_node_id, session_id, created_at "
                "FROM nodes ORDER BY created_at"
            ).fetchall()
        return [self._node_from_row(r) for r in rows]

    def get_edges(self) -> list[tuple[str, str]]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT parent_node_id, node_id "
                "FROM nodes WHERE parent_node_id IS NOT NULL"
            ).fetchall()
        return [(r["parent_node_id"], r["node_id"]) for r in rows]

    def active_node_ids(self) -> set[str]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT active_node_id FROM sessions"
            ).fetchall()
        return {r["active_node_id"] for r in rows}
