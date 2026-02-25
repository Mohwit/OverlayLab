from __future__ import annotations

import os
import platform
import time
from pathlib import Path

from app.core.errors import AppError
from app.core.models import NodeRecord
from app.utils.subprocess_safe import run_command


class OverlayManager:
    def __init__(self, nodes_root: Path, modules_root: Path | None = None):
        self.nodes_root = nodes_root.resolve()
        self.modules_root = (modules_root or Path("/lib/modules")).resolve()
        self._last_access: dict[str, float] = {}

    def _overlay_in_proc_filesystems(self) -> bool:
        proc_filesystems = Path("/proc/filesystems")
        if not proc_filesystems.exists():
            return False
        try:
            content = proc_filesystems.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
        return "overlay" in content

    def _overlay_module_available(self) -> bool:
        module_dir = self.modules_root / platform.release() / "kernel" / "fs" / "overlayfs"
        if not module_dir.exists():
            return False
        return any(module_dir.glob("overlay.ko*"))

    def _overlay_supported(self) -> bool:
        return self._overlay_in_proc_filesystems() or self._overlay_module_available()

    def preflight(self) -> dict[str, object]:
        linux = platform.system().lower() == "linux"
        overlay_supported = linux and self._overlay_supported()
        mount_capable = linux and os.geteuid() == 0

        msg = "OverlayFS available."
        if not linux:
            msg = "Linux is required for kernel OverlayFS mounts."
        elif not overlay_supported:
            msg = "OverlayFS support not detected in /proc/filesystems and no overlay module file found."
        elif not mount_capable:
            msg = "Mounting requires root privileges in this implementation."

        return {
            "linux": linux,
            "overlay_supported": overlay_supported,
            "mount_capable": mount_capable,
            "message": msg,
        }

    def ensure_supported(self) -> None:
        status = self.preflight()
        if not status["linux"] or not status["overlay_supported"]:
            raise AppError("OVERLAY_NOT_SUPPORTED", str(status["message"]), status_code=400)

    def is_mounted(self, merged_path: str | Path) -> bool:
        merged = str(Path(merged_path).resolve())
        mounts = Path("/proc/self/mounts")
        if not mounts.exists():
            return False
        for line in mounts.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == merged:
                return True
        return False

    def mount_node(self, node: NodeRecord) -> None:
        self.ensure_supported()
        if self.is_mounted(node.merged):
            self.touch(node.node_id)
            return

        options = f"lowerdir={':'.join(node.lowerdirs)},upperdir={node.upperdir},workdir={node.workdir}"
        result = run_command([
            "mount",
            "-t",
            "overlay",
            "overlay",
            "-o",
            options,
            node.merged,
        ])
        if result.returncode != 0:
            raise AppError(
                "MOUNT_FAILED",
                "Failed to mount overlay node.",
                details={"stderr": result.stderr.strip(), "stdout": result.stdout.strip()},
                status_code=500,
            )
        self.touch(node.node_id)

    def unmount_path(self, merged_path: str | Path) -> None:
        merged = str(Path(merged_path).resolve())
        if not self.is_mounted(merged):
            return

        result = run_command(["umount", merged])
        if result.returncode != 0:
            raise AppError(
                "UNMOUNT_FAILED",
                "Failed to unmount overlay node.",
                details={"stderr": result.stderr.strip(), "stdout": result.stdout.strip()},
                status_code=500,
            )

    def touch(self, node_id: str) -> None:
        self._last_access[node_id] = time.time()

    def clear_access_cache(self) -> None:
        self._last_access.clear()

    def last_access(self, node_id: str) -> float:
        return self._last_access.get(node_id, 0.0)

    def stale_node_ids(self, mounted_node_ids: list[str], active_node_ids: set[str], ttl_seconds: int) -> list[str]:
        now = time.time()
        stale = []
        for node_id in mounted_node_ids:
            if node_id in active_node_ids:
                continue
            if now - self.last_access(node_id) > ttl_seconds:
                stale.append(node_id)
        return stale

    def startup_cleanup_orphan_mounts(self, known_merged_paths: set[str]) -> None:
        mounts = Path("/proc/self/mounts")
        if not mounts.exists():
            return

        node_prefix = str(self.nodes_root)
        for line in mounts.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            mount_path = parts[1]
            fs_type = parts[2]
            if fs_type != "overlay":
                continue
            if not mount_path.startswith(node_prefix):
                continue
            if mount_path in known_merged_paths:
                continue
            run_command(["umount", mount_path])
