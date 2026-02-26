from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.errors import AppError
from app.services.db import Database


@dataclass(frozen=True, slots=True)
class FileRecord:
    """Represents a file entry from any layer (base, node upper, or merged)."""

    path: str
    content: bytes | None
    is_dir: bool
    size: int
    whiteout: bool
    created_at: str
    source: str


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteOverlayFS:
    """Core copy-on-write overlay engine backed by SQLite.

    Replaces kernel OverlayFS mounts with an in-process ancestry-chain
    walk over the ``base_files`` and ``node_files`` tables.  Every node
    has an implicit *upper layer* (its rows in ``node_files``) and an
    implicit set of *lower layers* derived from its parent chain.  The
    merged view is computed by stacking base -> oldest ancestor -> ...
    -> node, honouring whiteout markers for deletions.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Preflight
    # ------------------------------------------------------------------

    def preflight(self) -> dict[str, object]:
        """Return readiness status.  Always succeeds when the DB is writable."""
        try:
            with self._db.connect() as conn:
                conn.execute("SELECT 1")
            return {"ready": True, "message": "SQLite overlay engine is operational."}
        except Exception as exc:
            return {"ready": False, "message": f"SQLite error: {exc}"}

    # ------------------------------------------------------------------
    # Ancestry
    # ------------------------------------------------------------------

    def get_ancestry_chain(self, node_id: str) -> list[str]:
        """Return ``[node_id, parent_id, grandparent_id, ...]`` up to root."""
        chain: list[str] = []
        visited: set[str] = set()
        current: str | None = node_id

        with self._db.connect() as conn:
            while current is not None and current not in visited:
                chain.append(current)
                visited.add(current)
                row = conn.execute(
                    "SELECT parent_node_id FROM nodes WHERE node_id = ?",
                    (current,),
                ).fetchone()
                if row is None:
                    break
                current = row["parent_node_id"]

        return chain

    # ------------------------------------------------------------------
    # Base layer helpers
    # ------------------------------------------------------------------

    def get_base_files(self) -> list[FileRecord]:
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT path, content, is_dir, size, created_at FROM base_files ORDER BY path"
            ).fetchall()
        return [
            FileRecord(
                path=r["path"],
                content=r["content"],
                is_dir=bool(r["is_dir"]),
                size=r["size"],
                whiteout=False,
                created_at=r["created_at"],
                source="base",
            )
            for r in rows
        ]

    def add_base_file(
        self, path: str, content: bytes | None, *, is_dir: bool = False
    ) -> None:
        """Insert or replace a file in the shared base layer."""
        size = len(content) if content else 0
        with self._db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO base_files (path, content, is_dir, size, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (path, content, int(is_dir), size, _now_utc()),
            )

    def remove_base_file(self, path: str) -> None:
        """Remove a file from the shared base layer."""
        with self._db.connect() as conn:
            conn.execute("DELETE FROM base_files WHERE path = ?", (path,))

    # ------------------------------------------------------------------
    # Node upper-layer helpers
    # ------------------------------------------------------------------

    def get_node_upper_files(self, node_id: str) -> list[FileRecord]:
        """Return the files written directly in *this* node's upper layer."""
        with self._db.connect() as conn:
            rows = conn.execute(
                "SELECT path, content, is_dir, size, whiteout, created_at "
                "FROM node_files WHERE node_id = ? ORDER BY path",
                (node_id,),
            ).fetchall()
        return [
            FileRecord(
                path=r["path"],
                content=r["content"],
                is_dir=bool(r["is_dir"]),
                size=r["size"],
                whiteout=bool(r["whiteout"]),
                created_at=r["created_at"],
                source=node_id,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Merged-view resolution (core COW algorithm)
    # ------------------------------------------------------------------

    def resolve_merged_files(self, node_id: str) -> dict[str, FileRecord]:
        """Compute the full merged view for *node_id*.

        Walk order: base layer first, then ancestors oldest-to-newest,
        applying writes and whiteout deletions at each level.
        """
        ancestry = self.get_ancestry_chain(node_id)
        merged: dict[str, FileRecord] = {}

        for bf in self.get_base_files():
            merged[bf.path] = bf

        for ancestor_id in reversed(ancestry):
            for entry in self.get_node_upper_files(ancestor_id):
                if entry.whiteout:
                    merged.pop(entry.path, None)
                else:
                    merged[entry.path] = entry

        return merged

    def resolve_file(self, node_id: str, path: str) -> FileRecord | None:
        """Resolve a single file through the COW ancestry chain.

        Checks the node's own upper layer first, then walks up to each
        ancestor, and finally falls back to the base layer.  Returns
        ``None`` when the file does not exist or has been whited-out.
        """
        ancestry = self.get_ancestry_chain(node_id)

        with self._db.connect() as conn:
            for ancestor_id in ancestry:
                row = conn.execute(
                    "SELECT path, content, is_dir, size, whiteout, created_at "
                    "FROM node_files WHERE node_id = ? AND path = ?",
                    (ancestor_id, path),
                ).fetchone()
                if row is not None:
                    if row["whiteout"]:
                        return None
                    return FileRecord(
                        path=row["path"],
                        content=row["content"],
                        is_dir=bool(row["is_dir"]),
                        size=row["size"],
                        whiteout=False,
                        created_at=row["created_at"],
                        source=ancestor_id,
                    )

            row = conn.execute(
                "SELECT path, content, is_dir, size, created_at "
                "FROM base_files WHERE path = ?",
                (path,),
            ).fetchone()
            if row is not None:
                return FileRecord(
                    path=row["path"],
                    content=row["content"],
                    is_dir=bool(row["is_dir"]),
                    size=row["size"],
                    whiteout=False,
                    created_at=row["created_at"],
                    source="base",
                )

        return None

    # ------------------------------------------------------------------
    # Write / Delete (always target the given node's upper layer)
    # ------------------------------------------------------------------

    def write_file(
        self,
        node_id: str,
        path: str,
        content: bytes,
        *,
        is_dir: bool = False,
    ) -> int:
        """Write (or overwrite) a file in the node's upper layer.

        Returns the number of bytes written.
        """
        size = len(content) if content else 0
        now = _now_utc()
        with self._db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO node_files "
                "(node_id, path, content, is_dir, size, whiteout, created_at) "
                "VALUES (?, ?, ?, ?, ?, 0, ?)",
                (node_id, path, content, int(is_dir), size, now),
            )
        return size

    def delete_file(self, node_id: str, path: str) -> None:
        """Record a whiteout deletion in the node's upper layer.

        The file may live in a lower layer or the base layer; the
        whiteout marker hides it from the merged view without removing
        the original data.
        """
        record = self.resolve_file(node_id, path)
        if record is None:
            raise AppError(
                "INVALID_FILE_PATH",
                "File does not exist in the merged view for this node.",
                status_code=404,
            )
        if record.is_dir:
            raise AppError(
                "INVALID_FILE_PATH",
                "Deleting directories is not supported.",
                status_code=400,
            )
        now = _now_utc()
        with self._db.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO node_files "
                "(node_id, path, content, is_dir, size, whiteout, created_at) "
                "VALUES (?, ?, NULL, 0, 0, 1, ?)",
                (node_id, path, now),
            )

    # ------------------------------------------------------------------
    # Layer-specific queries (for the Layer Inspector UI)
    # ------------------------------------------------------------------

    def list_layer_files(
        self,
        node_id: str,
        layer: str,
        index: int | None = None,
    ) -> list[FileRecord]:
        """Return files visible in a specific layer.

        *layer* must be one of ``"merged"``, ``"upper"``, or ``"lower"``.
        For ``"lower"`` an *index* is required: ``0`` is the immediate
        parent's upper layer, ``1`` is the grandparent's, and so on.
        The base layer is the last index in the ancestry.
        """
        if layer == "merged":
            merged = self.resolve_merged_files(node_id)
            return sorted(merged.values(), key=lambda f: f.path)

        if layer == "upper":
            return [
                f for f in self.get_node_upper_files(node_id) if not f.whiteout
            ]

        if layer == "lower":
            ancestry = self.get_ancestry_chain(node_id)
            lower_ids = ancestry[1:]
            lower_count = len(lower_ids) + 1

            if index is None:
                raise AppError(
                    "INVALID_FILE_PATH",
                    "Lower-layer index is required.",
                    status_code=400,
                )
            if index < 0 or index >= lower_count:
                raise AppError(
                    "INVALID_FILE_PATH",
                    f"Lower-layer index out of range (0..{lower_count - 1}).",
                    status_code=400,
                )

            if index < len(lower_ids):
                return [
                    f
                    for f in self.get_node_upper_files(lower_ids[index])
                    if not f.whiteout
                ]
            return self.get_base_files()

        raise AppError(
            "INVALID_FILE_PATH",
            f"Unknown layer '{layer}'. Expected merged, upper, or lower.",
            status_code=400,
        )

    def get_lower_layer_count(self, node_id: str) -> int:
        """Number of lower layers: ancestors + base."""
        ancestry = self.get_ancestry_chain(node_id)
        return len(ancestry)

    def get_lower_layer_labels(self, node_id: str) -> list[str]:
        """Human-readable labels for each lower layer (for UI display).

        Index 0 = immediate parent's upper, last = base.
        """
        ancestry = self.get_ancestry_chain(node_id)
        labels: list[str] = []
        for ancestor_id in ancestry[1:]:
            labels.append(f"node:{ancestor_id}/upper")
        labels.append("base")
        return labels
