from __future__ import annotations

from app.services.db import Database
from app.services.file_service import FileService
from app.services.graph_store import GraphStore
from app.services.sqlite_overlay import SqliteOverlayFS


class ServiceContainer:
    def __init__(self):
        self.db = Database()
        self.db.init_schema()
        self.sqlite_overlay = SqliteOverlayFS(self.db)
        self.graph_store = GraphStore(self.db)
        self.file_service = FileService(self.sqlite_overlay)


container = ServiceContainer()
