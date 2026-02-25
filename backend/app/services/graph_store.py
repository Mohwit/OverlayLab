from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path

from app.core.models import NodeRecord, SessionFile, SessionRecord

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
    def __init__(self, base_dir: Path, nodes_dir: Path, sessions_dir: Path):
        self.base_dir = base_dir.resolve()
        self.nodes_dir = nodes_dir.resolve()
        self.sessions_dir = sessions_dir.resolve()
        self._lock = threading.RLock()
        self.sessions: dict[str, SessionRecord] = {}
        self.nodes: dict[str, NodeRecord] = {}

    def ensure_layout(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        with self._lock:
            self.ensure_layout()
            self.sessions.clear()
            self.nodes.clear()

            for file in sorted(self.sessions_dir.glob("*.json")):
                payload = json.loads(file.read_text(encoding="utf-8"))
                session_file = SessionFile.model_validate(payload)
                self.sessions[session_file.session.session_id] = session_file.session
                for node in session_file.nodes:
                    self.nodes[node.node_id] = node
            self._normalize_lowerdir_references()

    def _node_by_merged_path(self, merged_path: str) -> NodeRecord | None:
        for node in self.nodes.values():
            if node.merged == merged_path:
                return node
        return None

    def _expand_lowerdirs(self, lowerdirs: list[str], visited_node_ids: set[str]) -> list[str]:
        expanded: list[str] = []
        for lower in lowerdirs:
            source_node = self._node_by_merged_path(lower)
            if source_node and source_node.node_id not in visited_node_ids:
                nested = self._expand_lowerdirs(
                    [source_node.upperdir, *source_node.lowerdirs],
                    visited_node_ids | {source_node.node_id},
                )
                expanded.extend(nested)
            else:
                expanded.append(lower)

        # Preserve order while removing duplicates after expansion.
        seen: set[str] = set()
        normalized: list[str] = []
        for path in expanded:
            if path in seen:
                continue
            seen.add(path)
            normalized.append(path)
        return normalized

    def _normalize_lowerdir_references(self) -> None:
        changed_session_ids: set[str] = set()
        for node in self.nodes.values():
            normalized = self._expand_lowerdirs(node.lowerdirs, {node.node_id})
            if normalized == node.lowerdirs:
                continue
            node.lowerdirs = normalized
            changed_session_ids.add(node.session_id)
        for session_id in changed_session_ids:
            self._save_session(session_id)

    def _session_file_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def _save_session(self, session_id: str) -> None:
        session = self.sessions[session_id]
        nodes = sorted(
            [n for n in self.nodes.values() if n.session_id == session_id],
            key=lambda item: item.created_at,
        )
        session_file = SessionFile(session=session, nodes=nodes)
        self._session_file_path(session_id).write_text(
            json.dumps(session_file.model_dump(), indent=2),
            encoding="utf-8",
        )

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def _session_color(self) -> str:
        return SESSION_COLORS[len(self.sessions) % len(SESSION_COLORS)]

    def create_node_dirs(self, node_id: str) -> dict[str, str]:
        root = self.nodes_dir / node_id
        upper = root / "upper"
        work = root / "work"
        merged = root / "merged"
        upper.mkdir(parents=True, exist_ok=True)
        work.mkdir(parents=True, exist_ok=True)
        merged.mkdir(parents=True, exist_ok=True)
        return {
            "upperdir": str(upper.resolve()),
            "workdir": str(work.resolve()),
            "merged": str(merged.resolve()),
        }

    def create_session(self, name: str | None = None, from_node_id: str | None = None) -> tuple[SessionRecord, NodeRecord]:
        with self._lock:
            session_id = self._new_id("sess")
            node_id = self._new_id("node")
            dirs = self.create_node_dirs(node_id)

            parent_node_id = from_node_id
            lowerdirs = [str(self.base_dir.resolve())]
            if from_node_id:
                source = self.nodes[from_node_id]
                lowerdirs = self._expand_lowerdirs([source.upperdir, *source.lowerdirs], {source.node_id})

            root_node = NodeRecord(
                node_id=node_id,
                parent_node_id=parent_node_id,
                session_id=session_id,
                lowerdirs=lowerdirs,
                upperdir=dirs["upperdir"],
                workdir=dirs["workdir"],
                merged=dirs["merged"],
                mount_state="unmounted",
            )
            session = SessionRecord(
                session_id=session_id,
                name=name,
                root_node_id=node_id,
                active_node_id=node_id,
                color=self._session_color(),
            )

            self.sessions[session_id] = session
            self.nodes[node_id] = root_node
            self._save_session(session_id)
            return session, root_node

    def create_node(self, session_id: str, from_node_id: str) -> NodeRecord:
        with self._lock:
            node_id = self._new_id("node")
            dirs = self.create_node_dirs(node_id)
            parent = self.nodes[from_node_id]
            lowerdirs = self._expand_lowerdirs([parent.upperdir, *parent.lowerdirs], {parent.node_id})
            node = NodeRecord(
                node_id=node_id,
                parent_node_id=parent.node_id,
                session_id=session_id,
                lowerdirs=lowerdirs,
                upperdir=dirs["upperdir"],
                workdir=dirs["workdir"],
                merged=dirs["merged"],
                mount_state="unmounted",
            )
            self.nodes[node_id] = node
            self.sessions[session_id].active_node_id = node_id
            self._save_session(session_id)
            return node

    def set_active_node(self, session_id: str, node_id: str) -> None:
        with self._lock:
            self.sessions[session_id].active_node_id = node_id
            self._save_session(session_id)

    def update_node(self, node: NodeRecord) -> None:
        with self._lock:
            self.nodes[node.node_id] = node
            self._save_session(node.session_id)

    def reset_graph(self) -> dict[str, int]:
        with self._lock:
            cleared_nodes = len(self.nodes)
            cleared_sessions = len(self.sessions)

            self.sessions.clear()
            self.nodes.clear()
            self.ensure_layout()

            for session_file in self.sessions_dir.glob("*.json"):
                session_file.unlink(missing_ok=True)

            for entry in self.nodes_dir.iterdir():
                if entry.is_dir() and not entry.is_symlink():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink(missing_ok=True)

            return {"nodes": cleared_nodes, "sessions": cleared_sessions}

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self.sessions.get(session_id)

    def get_node(self, node_id: str) -> NodeRecord | None:
        return self.nodes.get(node_id)

    def get_all_sessions(self) -> list[SessionRecord]:
        return sorted(self.sessions.values(), key=lambda item: item.created_at)

    def get_all_nodes(self) -> list[NodeRecord]:
        return sorted(self.nodes.values(), key=lambda item: item.created_at)

    def get_edges(self) -> list[tuple[str, str]]:
        edges: list[tuple[str, str]] = []
        for node in self.nodes.values():
            if node.parent_node_id:
                edges.append((node.parent_node_id, node.node_id))
        return edges

    def active_node_ids(self) -> set[str]:
        return {session.active_node_id for session in self.sessions.values()}
