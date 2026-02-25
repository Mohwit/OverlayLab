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


def test_create_node_flattens_legacy_merged_lowerdirs(tmp_path: Path):
    store = GraphStore(tmp_path / "base", tmp_path / "nodes", tmp_path / "sessions")
    store.load()

    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)

    # Simulate legacy persisted node layout that used parent merged as lowerdir.
    child.lowerdirs = [root.merged]
    store.update_node(child)

    grandchild = store.create_node(session.session_id, child.node_id)

    assert root.merged not in grandchild.lowerdirs
    assert grandchild.lowerdirs[0] == child.upperdir
    assert root.upperdir in grandchild.lowerdirs
    assert str((tmp_path / "base").resolve()) in grandchild.lowerdirs


def test_load_normalizes_legacy_merged_lowerdirs(tmp_path: Path):
    store = GraphStore(tmp_path / "base", tmp_path / "nodes", tmp_path / "sessions")
    store.load()

    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)

    # Simulate legacy persisted node layout that used parent merged as lowerdir.
    child.lowerdirs = [root.merged]
    store.update_node(child)

    reloaded = GraphStore(tmp_path / "base", tmp_path / "nodes", tmp_path / "sessions")
    reloaded.load()

    normalized_child = reloaded.get_node(child.node_id)
    assert normalized_child is not None
    assert normalized_child.lowerdirs == [root.upperdir, str((tmp_path / "base").resolve())]


def test_reset_graph_clears_persisted_sessions_and_nodes(tmp_path: Path):
    store = GraphStore(tmp_path / "base", tmp_path / "nodes", tmp_path / "sessions")
    store.load()

    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)
    (Path(child.upperdir) / "note.md").write_text("hello", encoding="utf-8")

    summary = store.reset_graph()

    assert summary == {"nodes": 2, "sessions": 1}
    assert store.get_all_nodes() == []
    assert store.get_all_sessions() == []
    assert list((tmp_path / "sessions").glob("*.json")) == []
    assert list((tmp_path / "nodes").iterdir()) == []
