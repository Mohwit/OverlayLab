from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.schemas import (
    BranchSessionRequest,
    BranchSessionResponse,
    EdgeDTO,
    GraphDelta,
    NodeDTO,
    SessionDTO,
    SessionCreateRequest,
    SessionCreateResponse,
)

router = APIRouter(tags=["sessions"])


@router.post("/session/create", response_model=SessionCreateResponse)
def create_session(payload: SessionCreateRequest, container=Depends(get_container)):
    session, node = container.graph_store.create_session(name=payload.name)
    ancestry = container.sqlite_overlay.get_ancestry_chain(node.node_id)

    return SessionCreateResponse(
        session=SessionDTO(**session.model_dump()),
        root_node=NodeDTO.from_record(node, ancestry),
        graph_delta=GraphDelta(added_node_id=node.node_id),
    )


@router.post("/session/branch/{node_id}", response_model=BranchSessionResponse)
def branch_session(node_id: str, payload: BranchSessionRequest, container=Depends(get_container)):
    source = container.graph_store.get_node(node_id)
    if not source:
        from app.core.errors import AppError

        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    session, root_node = container.graph_store.create_session(name=payload.name, from_node_id=node_id)
    ancestry = container.sqlite_overlay.get_ancestry_chain(root_node.node_id)

    edge = EdgeDTO(source=node_id, target=root_node.node_id)
    return BranchSessionResponse(
        session=SessionDTO(**session.model_dump()),
        root_node=NodeDTO.from_record(root_node, ancestry),
        edge_from_source_node=edge,
    )
