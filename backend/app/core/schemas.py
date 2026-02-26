from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.models import NodeRecord


def _virtual_lowerdirs(node_id: str, ancestry: list[str]) -> list[str]:
    """Build virtual lowerdir labels from an ancestry chain.

    *ancestry* is ``[node_id, parent_id, grandparent_id, ...]``.
    Everything after the first entry becomes a lower-layer label,
    with the base layer appended at the end.
    """
    labels = [f"node:{aid}/upper" for aid in ancestry[1:]]
    labels.append("base")
    return labels


class ErrorDTO(BaseModel):
    code: str
    message: str
    details: Any | None = None


class NodeDTO(BaseModel):
    node_id: str
    parent_node_id: str | None
    session_id: str
    lowerdirs: list[str] = Field(default_factory=list)
    upperdir: str = ""
    workdir: str = ""
    merged: str = ""
    mount_state: Literal["mounted", "unmounted"] = "mounted"
    created_at: str

    @classmethod
    def from_record(
        cls, record: NodeRecord, ancestry: list[str] | None = None
    ) -> NodeDTO:
        if ancestry is None:
            ancestry = [record.node_id]
        return cls(
            node_id=record.node_id,
            parent_node_id=record.parent_node_id,
            session_id=record.session_id,
            lowerdirs=_virtual_lowerdirs(record.node_id, ancestry),
            upperdir=f"node:{record.node_id}/upper",
            workdir=f"node:{record.node_id}/work",
            merged=f"node:{record.node_id}/merged",
            mount_state="mounted",
            created_at=record.created_at,
        )


class SessionDTO(BaseModel):
    session_id: str
    name: str | None
    root_node_id: str
    active_node_id: str
    created_at: str
    color: str


class EdgeDTO(BaseModel):
    source: str
    target: str


class GraphDTO(BaseModel):
    sessions: list[SessionDTO]
    nodes: list[NodeDTO]
    edges: list[EdgeDTO]


class SessionCreateRequest(BaseModel):
    name: str | None = None


class NodeCreateRequest(BaseModel):
    session_id: str
    from_node_id: str | None = None


class BranchSessionRequest(BaseModel):
    name: str | None = None


class NodeRevertRequest(BaseModel):
    session_id: str


class FileEntryDTO(BaseModel):
    path: str
    type: Literal["file", "dir"]
    size: int
    mtime: float


class FilesResponse(BaseModel):
    node_id: str
    files: list[FileEntryDTO]


class FileContentResponse(BaseModel):
    node_id: str
    path: str
    content: str


class FileWriteRequest(BaseModel):
    path: str
    content: str = ""
    mode: Literal["overwrite", "append"] = "overwrite"


class FileWriteResponse(BaseModel):
    path: str
    bytes_written: int
    node_id: str


class FileDeleteRequest(BaseModel):
    path: str


class FileDeleteResponse(BaseModel):
    path: str
    deleted: bool


class LayerFilesResponse(BaseModel):
    node_id: str
    layer: Literal["merged", "upper", "lower"]
    index: int | None = None
    files: list[FileEntryDTO]


class LayerInfoDTO(BaseModel):
    node_id: str
    parent_node_id: str | None
    lowerdirs: list[str] = Field(default_factory=list)
    upperdir: str = ""
    workdir: str = ""
    merged: str = ""
    mount_state: Literal["mounted", "unmounted"] = "mounted"

    @classmethod
    def from_record(
        cls, record: NodeRecord, ancestry: list[str] | None = None
    ) -> LayerInfoDTO:
        if ancestry is None:
            ancestry = [record.node_id]
        return cls(
            node_id=record.node_id,
            parent_node_id=record.parent_node_id,
            lowerdirs=_virtual_lowerdirs(record.node_id, ancestry),
            upperdir=f"node:{record.node_id}/upper",
            workdir=f"node:{record.node_id}/work",
            merged=f"node:{record.node_id}/merged",
            mount_state="mounted",
        )


class GraphDelta(BaseModel):
    added_node_id: str | None = None
    added_edge: EdgeDTO | None = None


class SessionCreateResponse(BaseModel):
    session: SessionDTO
    root_node: NodeDTO
    graph_delta: GraphDelta


class NodeCreateResponse(BaseModel):
    node: NodeDTO
    session_active_node_id: str
    graph_delta: GraphDelta


class BranchSessionResponse(BaseModel):
    session: SessionDTO
    root_node: NodeDTO
    edge_from_source_node: EdgeDTO


class NodeRevertResponse(BaseModel):
    session_id: str
    active_node_id: str


class DiffFileDTO(BaseModel):
    path: str
    status: Literal["added", "removed", "modified", "unchanged"]
    diff: str


class DiffDTO(BaseModel):
    from_node_id: str
    to_node_id: str
    files: list[DiffFileDTO]


class HealthPreflightDTO(BaseModel):
    ready: bool
    message: str


class ResetResponseDTO(BaseModel):
    cleared_nodes: int
    cleared_sessions: int
    message: str
