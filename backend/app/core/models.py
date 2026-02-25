from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class NodeRecord(BaseModel):
    node_id: str
    parent_node_id: str | None = None
    session_id: str
    lowerdirs: list[str] = Field(default_factory=list)
    upperdir: str
    workdir: str
    merged: str
    mount_state: Literal["mounted", "unmounted"] = "unmounted"
    created_at: str = Field(default_factory=now_utc)


class SessionRecord(BaseModel):
    session_id: str
    name: str | None = None
    root_node_id: str
    active_node_id: str
    created_at: str = Field(default_factory=now_utc)
    color: str


class SessionFile(BaseModel):
    session: SessionRecord
    nodes: list[NodeRecord]
