from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.container import ServiceContainer


class FakeOverlayManager:
    def __init__(self):
        self._mounted: set[str] = set()
        self._last_access: dict[str, float] = {}

    def preflight(self):
        return {
            "linux": True,
            "overlay_supported": True,
            "mount_capable": True,
            "message": "ok",
        }

    def startup_cleanup_orphan_mounts(self, known_merged_paths):
        return None

    def is_mounted(self, merged):
        return str(merged) in self._mounted

    def mount_node(self, node):
        self._mounted.add(str(node.merged))

    def unmount_path(self, merged):
        self._mounted.discard(str(merged))

    def touch(self, node_id: str):
        self._last_access[node_id] = 10

    def stale_node_ids(self, mounted_node_ids, active_node_ids, ttl_seconds):
        return []


def build_test_client(tmp_path: Path) -> TestClient:
    container = ServiceContainer()
    container.graph_store = container.graph_store.__class__(
        tmp_path / "base",
        tmp_path / "nodes",
        tmp_path / "sessions",
    )
    container.graph_store.load()
    container.overlay_manager = FakeOverlayManager()

    from app.api.deps import get_container

    app.dependency_overrides[get_container] = lambda: container
    return TestClient(app)


def test_session_create_and_file_ops(tmp_path: Path):
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "demo"})
    assert session_resp.status_code == 200
    node_id = session_resp.json()["root_node"]["node_id"]

    write_resp = client.post(
        f"/node/{node_id}/file",
        json={"path": "note.md", "content": "hello", "mode": "overwrite"},
    )
    assert write_resp.status_code == 200

    files_resp = client.get(f"/node/{node_id}/files")
    assert files_resp.status_code == 200
    paths = [entry["path"] for entry in files_resp.json()["files"] if entry["type"] == "file"]
    assert "note.md" in paths


def test_invalid_path_rejected(tmp_path: Path):
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "demo"})
    node_id = session_resp.json()["root_node"]["node_id"]

    write_resp = client.post(
        f"/node/{node_id}/file",
        json={"path": "../secret.md", "content": "bad", "mode": "overwrite"},
    )
    assert write_resp.status_code == 400
