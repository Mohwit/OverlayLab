from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.services.cleanup import CleanupWorker
from app.services.file_service import FileService
from app.services.graph_store import GraphStore
from app.services.overlay_manager import OverlayManager


class ServiceContainer:
    def __init__(self):
        root = Path(settings.overlay_root)
        base = root / "base"
        nodes = root / "nodes"
        sessions = root / "sessions"

        self.graph_store = GraphStore(base, nodes, sessions)
        self.overlay_manager = OverlayManager(nodes_root=nodes)
        self.file_service = FileService()
        self.cleanup_worker = CleanupWorker(self.graph_store, self.overlay_manager)


container = ServiceContainer()
