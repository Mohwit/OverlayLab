from pathlib import Path

from app.services.overlay_manager import OverlayManager


def test_stale_node_selection(tmp_path: Path):
    manager = OverlayManager(nodes_root=tmp_path)
    manager._last_access["a"] = 0
    manager._last_access["b"] = 10**9

    stale = manager.stale_node_ids(
        mounted_node_ids=["a", "b", "c"],
        active_node_ids={"c"},
        ttl_seconds=1,
    )

    assert "a" in stale
    assert "b" not in stale
    assert "c" not in stale


def test_is_mounted_non_linux_path(tmp_path: Path):
    manager = OverlayManager(nodes_root=tmp_path)
    assert manager.is_mounted(tmp_path / "missing") is False
