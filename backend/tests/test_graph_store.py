from pathlib import Path

from app.services.graph_store import GraphStore


def test_graph_store_persist_and_reload(tmp_path: Path):
    store = GraphStore(tmp_path / "base", tmp_path / "nodes", tmp_path / "sessions")
    store.load()

    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)
    store.set_active_node(session.session_id, child.node_id)

    reloaded = GraphStore(tmp_path / "base", tmp_path / "nodes", tmp_path / "sessions")
    reloaded.load()

    assert reloaded.get_session(session.session_id) is not None
    assert reloaded.get_node(root.node_id) is not None
    assert reloaded.get_node(child.node_id) is not None
    assert reloaded.get_session(session.session_id).active_node_id == child.node_id
