import pytest

from app.services.db import Database
from app.services.graph_store import GraphStore
from app.services.sqlite_overlay import SqliteOverlayFS


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "recall.db")
    database.init_schema()
    return database


@pytest.fixture
def overlay(db):
    return SqliteOverlayFS(db)


@pytest.fixture
def store(db):
    return GraphStore(db)


# ------------------------------------------------------------------
# Preflight
# ------------------------------------------------------------------

def test_preflight_returns_ready(overlay):
    result = overlay.preflight()
    assert result["ready"] is True
    assert "message" in result


# ------------------------------------------------------------------
# Base layer
# ------------------------------------------------------------------

def test_add_and_get_base_files(overlay):
    overlay.add_base_file("readme.md", b"# Hello")
    overlay.add_base_file("notes.txt", b"some notes")

    files = overlay.get_base_files()
    paths = [f.path for f in files]
    assert "notes.txt" in paths
    assert "readme.md" in paths

    readme = next(f for f in files if f.path == "readme.md")
    assert readme.content == b"# Hello"
    assert readme.source == "base"
    assert readme.whiteout is False


def test_remove_base_file(overlay):
    overlay.add_base_file("tmp.txt", b"data")
    overlay.remove_base_file("tmp.txt")

    files = overlay.get_base_files()
    assert all(f.path != "tmp.txt" for f in files)


def test_add_base_dir(overlay):
    overlay.add_base_file("docs", None, is_dir=True)
    files = overlay.get_base_files()
    docs = next(f for f in files if f.path == "docs")
    assert docs.is_dir is True
    assert docs.size == 0


# ------------------------------------------------------------------
# Ancestry chain
# ------------------------------------------------------------------

def test_ancestry_chain_single_node(overlay, store):
    _session, root = store.create_session(name="A")
    chain = overlay.get_ancestry_chain(root.node_id)
    assert chain == [root.node_id]


def test_ancestry_chain_with_children(overlay, store):
    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)
    grandchild = store.create_node(session.session_id, child.node_id)

    chain = overlay.get_ancestry_chain(grandchild.node_id)
    assert chain == [grandchild.node_id, child.node_id, root.node_id]


def test_ancestry_chain_across_branched_sessions(overlay, store):
    session_a, root_a = store.create_session(name="A")
    child_a = store.create_node(session_a.session_id, root_a.node_id)

    _session_b, root_b = store.create_session(name="B", from_node_id=child_a.node_id)

    chain = overlay.get_ancestry_chain(root_b.node_id)
    assert chain == [root_b.node_id, child_a.node_id, root_a.node_id]


def test_ancestry_chain_unknown_node_returns_self_only(overlay):
    chain = overlay.get_ancestry_chain("nonexistent")
    assert chain == ["nonexistent"]


# ------------------------------------------------------------------
# Write / resolve single file
# ------------------------------------------------------------------

def test_write_and_resolve_file(overlay, store):
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "hello.txt", b"world")

    record = overlay.resolve_file(root.node_id, "hello.txt")
    assert record is not None
    assert record.content == b"world"
    assert record.source == root.node_id


def test_resolve_file_falls_through_to_base(overlay, store):
    overlay.add_base_file("base.md", b"base content")
    _session, root = store.create_session(name="A")

    record = overlay.resolve_file(root.node_id, "base.md")
    assert record is not None
    assert record.content == b"base content"
    assert record.source == "base"


def test_resolve_file_returns_none_for_missing(overlay, store):
    _session, root = store.create_session(name="A")
    assert overlay.resolve_file(root.node_id, "missing.txt") is None


# ------------------------------------------------------------------
# Copy-on-write: child overrides parent
# ------------------------------------------------------------------

def test_child_overrides_parent_file(overlay, store):
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "data.txt", b"v1")

    child = store.create_node(session.session_id, root.node_id)
    overlay.write_file(child.node_id, "data.txt", b"v2")

    parent_record = overlay.resolve_file(root.node_id, "data.txt")
    assert parent_record.content == b"v1"

    child_record = overlay.resolve_file(child.node_id, "data.txt")
    assert child_record.content == b"v2"
    assert child_record.source == child.node_id


def test_child_inherits_parent_file(overlay, store):
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "shared.txt", b"from parent")

    child = store.create_node(session.session_id, root.node_id)

    record = overlay.resolve_file(child.node_id, "shared.txt")
    assert record is not None
    assert record.content == b"from parent"
    assert record.source == root.node_id


# ------------------------------------------------------------------
# Whiteout (deletion markers)
# ------------------------------------------------------------------

def test_whiteout_hides_parent_file(overlay, store):
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "secret.txt", b"classified")

    child = store.create_node(session.session_id, root.node_id)
    overlay.delete_file(child.node_id, "secret.txt")

    assert overlay.resolve_file(root.node_id, "secret.txt") is not None
    assert overlay.resolve_file(child.node_id, "secret.txt") is None


def test_whiteout_hides_base_file(overlay, store):
    overlay.add_base_file("base.txt", b"base data")
    session, root = store.create_session(name="A")

    overlay.delete_file(root.node_id, "base.txt")

    assert overlay.resolve_file(root.node_id, "base.txt") is None


def test_whiteout_excluded_from_merged_view(overlay, store):
    overlay.add_base_file("keep.txt", b"keep")
    overlay.add_base_file("remove.txt", b"remove")

    session, root = store.create_session(name="A")
    overlay.delete_file(root.node_id, "remove.txt")

    merged = overlay.resolve_merged_files(root.node_id)
    assert "keep.txt" in merged
    assert "remove.txt" not in merged


def test_delete_nonexistent_file_raises(overlay, store):
    _session, root = store.create_session(name="A")
    with pytest.raises(Exception, match="does not exist"):
        overlay.delete_file(root.node_id, "ghost.txt")


def test_delete_directory_raises(overlay, store):
    overlay.add_base_file("mydir", None, is_dir=True)
    _session, root = store.create_session(name="A")
    with pytest.raises(Exception, match="not supported"):
        overlay.delete_file(root.node_id, "mydir")


# ------------------------------------------------------------------
# Merged view resolution
# ------------------------------------------------------------------

def test_merged_view_combines_base_and_upper(overlay, store):
    overlay.add_base_file("base.txt", b"from base")
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "upper.txt", b"from upper")

    merged = overlay.resolve_merged_files(root.node_id)
    assert "base.txt" in merged
    assert "upper.txt" in merged
    assert merged["base.txt"].source == "base"
    assert merged["upper.txt"].source == root.node_id


def test_merged_view_deep_ancestry(overlay, store):
    overlay.add_base_file("base.md", b"base")
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "root.md", b"root")

    child = store.create_node(session.session_id, root.node_id)
    overlay.write_file(child.node_id, "child.md", b"child")

    grandchild = store.create_node(session.session_id, child.node_id)
    overlay.write_file(grandchild.node_id, "gc.md", b"grandchild")

    merged = overlay.resolve_merged_files(grandchild.node_id)
    assert set(merged.keys()) == {"base.md", "root.md", "child.md", "gc.md"}


def test_merged_view_override_chain(overlay, store):
    overlay.add_base_file("file.txt", b"base-version")
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "file.txt", b"root-version")

    child = store.create_node(session.session_id, root.node_id)
    overlay.write_file(child.node_id, "file.txt", b"child-version")

    merged = overlay.resolve_merged_files(child.node_id)
    assert merged["file.txt"].content == b"child-version"
    assert merged["file.txt"].source == child.node_id


# ------------------------------------------------------------------
# Node upper-layer files
# ------------------------------------------------------------------

def test_get_node_upper_files(overlay, store):
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "a.txt", b"aaa")
    overlay.write_file(root.node_id, "b.txt", b"bbb")

    upper = overlay.get_node_upper_files(root.node_id)
    paths = [f.path for f in upper]
    assert "a.txt" in paths
    assert "b.txt" in paths
    assert len(upper) == 2


def test_upper_includes_whiteout_markers(overlay, store):
    overlay.add_base_file("doomed.txt", b"data")
    session, root = store.create_session(name="A")
    overlay.delete_file(root.node_id, "doomed.txt")

    upper = overlay.get_node_upper_files(root.node_id)
    assert len(upper) == 1
    assert upper[0].whiteout is True
    assert upper[0].path == "doomed.txt"


# ------------------------------------------------------------------
# Layer-specific queries (Layer Inspector support)
# ------------------------------------------------------------------

def test_list_layer_merged(overlay, store):
    overlay.add_base_file("base.txt", b"b")
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "new.txt", b"n")

    files = overlay.list_layer_files(root.node_id, "merged")
    paths = [f.path for f in files]
    assert "base.txt" in paths
    assert "new.txt" in paths


def test_list_layer_upper(overlay, store):
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "upper.txt", b"u")

    files = overlay.list_layer_files(root.node_id, "upper")
    assert len(files) == 1
    assert files[0].path == "upper.txt"


def test_list_layer_lower_parent(overlay, store):
    session, root = store.create_session(name="A")
    overlay.write_file(root.node_id, "parent.txt", b"p")

    child = store.create_node(session.session_id, root.node_id)
    files = overlay.list_layer_files(child.node_id, "lower", index=0)
    assert len(files) == 1
    assert files[0].path == "parent.txt"


def test_list_layer_lower_base(overlay, store):
    overlay.add_base_file("base.txt", b"b")
    session, root = store.create_session(name="A")

    files = overlay.list_layer_files(root.node_id, "lower", index=0)
    assert len(files) == 1
    assert files[0].path == "base.txt"


def test_list_layer_lower_missing_index_raises(overlay, store):
    _session, root = store.create_session(name="A")
    with pytest.raises(Exception, match="index is required"):
        overlay.list_layer_files(root.node_id, "lower", index=None)


def test_list_layer_lower_out_of_range_raises(overlay, store):
    _session, root = store.create_session(name="A")
    with pytest.raises(Exception):
        overlay.list_layer_files(root.node_id, "lower", index=99)


def test_list_layer_unknown_raises(overlay, store):
    _session, root = store.create_session(name="A")
    with pytest.raises(Exception, match="Unknown layer"):
        overlay.list_layer_files(root.node_id, "bogus")


# ------------------------------------------------------------------
# Lower layer labels / count
# ------------------------------------------------------------------

def test_lower_layer_count_root(overlay, store):
    _session, root = store.create_session(name="A")
    assert overlay.get_lower_layer_count(root.node_id) == 1


def test_lower_layer_count_child(overlay, store):
    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)
    assert overlay.get_lower_layer_count(child.node_id) == 2


def test_lower_layer_labels(overlay, store):
    session, root = store.create_session(name="A")
    child = store.create_node(session.session_id, root.node_id)

    labels = overlay.get_lower_layer_labels(child.node_id)
    assert labels == [f"node:{root.node_id}/upper", "base"]


# ------------------------------------------------------------------
# Write returns byte count
# ------------------------------------------------------------------

def test_write_returns_size(overlay, store):
    _session, root = store.create_session(name="A")
    size = overlay.write_file(root.node_id, "test.txt", b"12345")
    assert size == 5


# ------------------------------------------------------------------
# Branch inherits full ancestry
# ------------------------------------------------------------------

def test_branch_inherits_files_through_ancestry(overlay, store):
    overlay.add_base_file("base.md", b"base")
    session_a, root_a = store.create_session(name="A")
    overlay.write_file(root_a.node_id, "a.txt", b"from a")

    child_a = store.create_node(session_a.session_id, root_a.node_id)
    overlay.write_file(child_a.node_id, "child.txt", b"from child")

    _session_b, root_b = store.create_session(name="B", from_node_id=child_a.node_id)

    merged = overlay.resolve_merged_files(root_b.node_id)
    assert "base.md" in merged
    assert "a.txt" in merged
    assert "child.txt" in merged
