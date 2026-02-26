import pytest

from app.services.db import Database
from app.services.graph_store import GraphStore


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "recall.db")
    database.init_schema()
    return database


@pytest.fixture
def store(db):
    return GraphStore(db)


def test_create_session_and_read_back(store):
    session, root = store.create_session(name="A")

    loaded_session = store.get_session(session.session_id)
    assert loaded_session is not None
    assert loaded_session.name == "A"
    assert loaded_session.root_node_id == root.node_id
    assert loaded_session.active_node_id == root.node_id

    loaded_node = store.get_node(root.node_id)
    assert loaded_node is not None
    assert loaded_node.session_id == session.session_id
    assert loaded_node.parent_node_id is None


def test_create_node_sets_parent_and_active(store):
    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)

    assert child.parent_node_id == root.node_id
    assert child.session_id == session.session_id

    updated_session = store.get_session(session.session_id)
    assert updated_session.active_node_id == child.node_id


def test_set_active_node(store):
    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)
    store.set_active_node(session.session_id, root.node_id)

    updated = store.get_session(session.session_id)
    assert updated.active_node_id == root.node_id


def test_branch_session_links_to_source_node(store):
    session_a, root_a = store.create_session(name="A")
    child_a = store.create_node(session_a.session_id, root_a.node_id)

    session_b, root_b = store.create_session(name="B", from_node_id=child_a.node_id)

    assert root_b.parent_node_id == child_a.node_id
    assert root_b.session_id == session_b.session_id


def test_reset_graph_clears_all_data(store):
    session, root = store.create_session(name="A")
    store.create_node(session.session_id, root.node_id)

    summary = store.reset_graph()

    assert summary == {"nodes": 2, "sessions": 1}
    assert store.get_all_nodes() == []
    assert store.get_all_sessions() == []


def test_get_edges(store):
    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)
    grandchild = store.create_node(session.session_id, child.node_id)

    edges = store.get_edges()
    assert (root.node_id, child.node_id) in edges
    assert (child.node_id, grandchild.node_id) in edges
    assert len(edges) == 2


def test_active_node_ids(store):
    session_a, _root_a = store.create_session(name="A")
    child_a = store.create_node(session_a.session_id, _root_a.node_id)

    _session_b, root_b = store.create_session(name="B")

    ids = store.active_node_ids()
    assert child_a.node_id in ids
    assert root_b.node_id in ids


def test_persistence_across_store_instances(db):
    store = GraphStore(db)
    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)
    store.set_active_node(session.session_id, child.node_id)

    store2 = GraphStore(db)
    store2.load()

    assert store2.get_session(session.session_id) is not None
    assert store2.get_node(root.node_id) is not None
    assert store2.get_node(child.node_id) is not None
    assert store2.get_session(session.session_id).active_node_id == child.node_id


def test_get_all_sessions_ordered(store):
    s1, _ = store.create_session(name="First")
    s2, _ = store.create_session(name="Second")

    sessions = store.get_all_sessions()
    assert len(sessions) == 2
    assert sessions[0].session_id == s1.session_id
    assert sessions[1].session_id == s2.session_id


def test_get_all_nodes_ordered(store):
    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)

    nodes = store.get_all_nodes()
    assert len(nodes) == 2
    assert nodes[0].node_id == root.node_id
    assert nodes[1].node_id == child.node_id


def test_update_node_is_noop(store):
    session, root = store.create_session(name="A")
    store.update_node(root)

    loaded = store.get_node(root.node_id)
    assert loaded is not None
    assert loaded.node_id == root.node_id


def test_session_color_cycles(store):
    colors = set()
    for i in range(10):
        session, _ = store.create_session(name=f"S{i}")
        colors.add(session.color)
    assert len(colors) >= 2
