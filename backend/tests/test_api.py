from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.container import ServiceContainer
from app.services.db import Database
from app.services.file_service import FileService
from app.services.graph_store import GraphStore
from app.services.sqlite_overlay import SqliteOverlayFS


def build_test_client(tmp_path: Path) -> TestClient:
    db = Database(tmp_path / "recall.db")
    db.init_schema()

    container = ServiceContainer.__new__(ServiceContainer)
    container.db = db
    container.sqlite_overlay = SqliteOverlayFS(db)
    container.graph_store = GraphStore(db)
    container.file_service = FileService(container.sqlite_overlay)

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


def test_health_preflight(tmp_path: Path):
    client = build_test_client(tmp_path)
    resp = client.get("/health/preflight")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True


def test_admin_reset(tmp_path: Path):
    client = build_test_client(tmp_path)

    client.post("/session/create", json={"name": "demo"})
    reset_resp = client.post("/admin/reset")
    assert reset_resp.status_code == 200
    data = reset_resp.json()
    assert data["cleared_sessions"] == 1
    assert data["cleared_nodes"] == 1


def test_graph_endpoint(tmp_path: Path):
    client = build_test_client(tmp_path)

    client.post("/session/create", json={"name": "A"})
    resp = client.get("/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sessions"]) == 1
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["mount_state"] == "mounted"


def test_node_create_and_revert(tmp_path: Path):
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "demo"})
    session_data = session_resp.json()
    session_id = session_data["session"]["session_id"]
    root_id = session_data["root_node"]["node_id"]

    node_resp = client.post(
        "/node/create",
        json={"session_id": session_id, "from_node_id": root_id},
    )
    assert node_resp.status_code == 200
    child_id = node_resp.json()["node"]["node_id"]

    revert_resp = client.post(
        f"/node/revert/{root_id}",
        json={"session_id": session_id},
    )
    assert revert_resp.status_code == 200
    assert revert_resp.json()["active_node_id"] == root_id


def test_branch_session(tmp_path: Path):
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "A"})
    root_id = session_resp.json()["root_node"]["node_id"]

    branch_resp = client.post(
        f"/session/branch/{root_id}",
        json={"name": "B"},
    )
    assert branch_resp.status_code == 200
    data = branch_resp.json()
    assert data["session"]["name"] == "B"
    assert data["root_node"]["parent_node_id"] == root_id


def test_file_read_and_delete(tmp_path: Path):
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "demo"})
    node_id = session_resp.json()["root_node"]["node_id"]

    client.post(
        f"/node/{node_id}/file",
        json={"path": "doc.md", "content": "some text", "mode": "overwrite"},
    )

    read_resp = client.get(f"/node/{node_id}/file", params={"path": "doc.md"})
    assert read_resp.status_code == 200
    assert read_resp.json()["content"] == "some text"

    del_resp = client.request(
        "DELETE",
        f"/node/{node_id}/file",
        json={"path": "doc.md"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True

    read_again = client.get(f"/node/{node_id}/file", params={"path": "doc.md"})
    assert read_again.status_code == 404


def test_diff_endpoint(tmp_path: Path):
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "demo"})
    session_data = session_resp.json()
    session_id = session_data["session"]["session_id"]
    root_id = session_data["root_node"]["node_id"]

    client.post(
        f"/node/{root_id}/file",
        json={"path": "file.md", "content": "v1", "mode": "overwrite"},
    )

    node_resp = client.post(
        "/node/create",
        json={"session_id": session_id, "from_node_id": root_id},
    )
    child_id = node_resp.json()["node"]["node_id"]

    client.post(
        f"/node/{child_id}/file",
        json={"path": "file.md", "content": "v2", "mode": "overwrite"},
    )

    diff_resp = client.get(
        "/diff",
        params={"from_node_id": root_id, "to_node_id": child_id},
    )
    assert diff_resp.status_code == 200
    data = diff_resp.json()
    assert len(data["files"]) == 1
    assert data["files"][0]["status"] == "modified"


def test_layer_files_endpoint(tmp_path: Path):
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "demo"})
    node_id = session_resp.json()["root_node"]["node_id"]

    client.post(
        f"/node/{node_id}/file",
        json={"path": "top.md", "content": "data", "mode": "overwrite"},
    )

    upper_resp = client.get(
        f"/node/{node_id}/layer-files",
        params={"layer": "upper"},
    )
    assert upper_resp.status_code == 200
    paths = [f["path"] for f in upper_resp.json()["files"]]
    assert "top.md" in paths


def test_layers_endpoint(tmp_path: Path):
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "demo"})
    node_id = session_resp.json()["root_node"]["node_id"]

    layers_resp = client.get(f"/node/{node_id}/layers")
    assert layers_resp.status_code == 200
    data = layers_resp.json()
    assert data["mount_state"] == "mounted"
    assert data["upperdir"] == f"node:{node_id}/upper"
    assert "base" in data["lowerdirs"]


def test_cow_visible_through_api(tmp_path: Path):
    """Child node sees parent's file, overrides it, and parent is unaffected."""
    client = build_test_client(tmp_path)

    session_resp = client.post("/session/create", json={"name": "cow"})
    session_data = session_resp.json()
    session_id = session_data["session"]["session_id"]
    root_id = session_data["root_node"]["node_id"]

    client.post(
        f"/node/{root_id}/file",
        json={"path": "shared.md", "content": "original", "mode": "overwrite"},
    )

    node_resp = client.post(
        "/node/create",
        json={"session_id": session_id, "from_node_id": root_id},
    )
    child_id = node_resp.json()["node"]["node_id"]

    child_read = client.get(f"/node/{child_id}/file", params={"path": "shared.md"})
    assert child_read.json()["content"] == "original"

    client.post(
        f"/node/{child_id}/file",
        json={"path": "shared.md", "content": "modified", "mode": "overwrite"},
    )

    parent_read = client.get(f"/node/{root_id}/file", params={"path": "shared.md"})
    assert parent_read.json()["content"] == "original"

    child_read2 = client.get(f"/node/{child_id}/file", params={"path": "shared.md"})
    assert child_read2.json()["content"] == "modified"
