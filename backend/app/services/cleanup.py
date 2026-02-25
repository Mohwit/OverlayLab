from __future__ import annotations

import asyncio
import contextlib

from app.core.config import settings
from app.services.graph_store import GraphStore
from app.services.overlay_manager import OverlayManager


class CleanupWorker:
    def __init__(self, graph_store: GraphStore, overlay_manager: OverlayManager):
        self.graph_store = graph_store
        self.overlay_manager = overlay_manager
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(settings.cleanup_interval_seconds)
            await self.cleanup_idle_mounts()

    async def cleanup_idle_mounts(self) -> None:
        active_ids = self.graph_store.active_node_ids()
        mounted_ids = [
            node.node_id
            for node in self.graph_store.get_all_nodes()
            if node.mount_state == "mounted"
        ]
        stale = self.overlay_manager.stale_node_ids(
            mounted_node_ids=mounted_ids,
            active_node_ids=active_ids,
            ttl_seconds=settings.mount_idle_ttl_seconds,
        )
        for node_id in stale:
            node = self.graph_store.get_node(node_id)
            if not node:
                continue
            try:
                self.overlay_manager.unmount_path(node.merged)
            except Exception:
                continue
            node.mount_state = "unmounted"
            self.graph_store.update_node(node)

    async def shutdown_unmount_all(self) -> None:
        for node in self.graph_store.get_all_nodes():
            if node.mount_state != "mounted":
                continue
            try:
                self.overlay_manager.unmount_path(node.merged)
            except Exception:
                continue
            node.mount_state = "unmounted"
            self.graph_store.update_node(node)
