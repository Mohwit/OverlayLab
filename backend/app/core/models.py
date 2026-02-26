from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class NodeRecord(BaseModel):
    node_id: str
    parent_node_id: str | None = None
    session_id: str
    created_at: str = Field(default_factory=now_utc)


class SessionRecord(BaseModel):
    session_id: str
    name: str | None = None
    root_node_id: str
    active_node_id: str
    created_at: str = Field(default_factory=now_utc)
    color: str
