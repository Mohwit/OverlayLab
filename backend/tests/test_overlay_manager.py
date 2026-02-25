from pathlib import Path

import pytest

from app.services.overlay_manager import OverlayManager


def test_stale_node_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manager = OverlayManager(nodes_root=tmp_path)
    manager._last_access["a"] = 0
    manager._last_access["b"] = 999
    monkeypatch.setattr("time.time", lambda: 1000)

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


def test_overlay_supported_with_module_file_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    kernel_release = "test-kernel"
    module_dir = tmp_path / "modules" / kernel_release / "kernel" / "fs" / "overlayfs"
    module_dir.mkdir(parents=True)
    (module_dir / "overlay.ko.zst").write_text("", encoding="utf-8")

    manager = OverlayManager(nodes_root=tmp_path, modules_root=tmp_path / "modules")
    monkeypatch.setattr("platform.release", lambda: kernel_release)
    monkeypatch.setattr(manager, "_overlay_in_proc_filesystems", lambda: False)

    assert manager._overlay_supported() is True


def test_preflight_message_when_overlay_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manager = OverlayManager(nodes_root=tmp_path)
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("os.geteuid", lambda: 0)
    monkeypatch.setattr(manager, "_overlay_supported", lambda: False)

    status = manager.preflight()

    assert status["overlay_supported"] is False
    assert status["message"] == "OverlayFS support not detected in /proc/filesystems and no overlay module file found."
