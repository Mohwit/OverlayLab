from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.errors import AppError
from app.core.schemas import (
    EdgeDTO,
    GraphDelta,
    LayerInfoDTO,
    NodeDTO,
    NodeCreateRequest,
    NodeCreateResponse,
    NodeRevertRequest,
    NodeRevertResponse,
)

router = APIRouter(tags=["nodes"])


@router.post("/node/create", response_model=NodeCreateResponse)
def create_node(payload: NodeCreateRequest, container=Depends(get_container)):
    session = container.graph_store.get_session(payload.session_id)
    if not session:
        raise AppError("SESSION_NOT_FOUND", f"Session {payload.session_id} not found.", status_code=404)

    from_node_id = payload.from_node_id or session.active_node_id
    parent_node = container.graph_store.get_node(from_node_id)
    if not parent_node:
        raise AppError("NODE_NOT_FOUND", f"Node {from_node_id} was not found.", status_code=404)
    if parent_node.session_id != payload.session_id:
        raise AppError("NODE_NOT_FOUND", "Source node must belong to the target session.", status_code=400)

    node = container.graph_store.create_node(session_id=payload.session_id, from_node_id=from_node_id)
    ancestry = container.sqlite_overlay.get_ancestry_chain(node.node_id)

    return NodeCreateResponse(
        node=NodeDTO.from_record(node, ancestry),
        session_active_node_id=node.node_id,
        graph_delta=GraphDelta(
            added_node_id=node.node_id,
            added_edge=EdgeDTO(source=from_node_id, target=node.node_id),
        ),
    )


@router.post("/node/revert/{node_id}", response_model=NodeRevertResponse)
def revert_node(node_id: str, payload: NodeRevertRequest, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    session = container.graph_store.get_session(payload.session_id)
    if not session:
        raise AppError("SESSION_NOT_FOUND", f"Session {payload.session_id} not found.", status_code=404)

    if node.session_id != session.session_id:
        raise AppError("NODE_NOT_FOUND", "Target node is not part of the selected session.", status_code=400)

    container.graph_store.set_active_node(payload.session_id, node_id)
    return NodeRevertResponse(session_id=payload.session_id, active_node_id=node_id)


@router.get("/node/{node_id}/layers", response_model=LayerInfoDTO)
def get_layers(node_id: str, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)
    ancestry = container.sqlite_overlay.get_ancestry_chain(node_id)
    return LayerInfoDTO.from_record(node, ancestry)


@router.get("/graph")
def get_graph(container=Depends(get_container)):
    sessions = container.graph_store.get_all_sessions()
    nodes = container.graph_store.get_all_nodes()
    edges = [EdgeDTO(source=s, target=t) for s, t in container.graph_store.get_edges()]

    node_dtos = []
    for n in nodes:
        ancestry = container.sqlite_overlay.get_ancestry_chain(n.node_id)
        node_dtos.append(NodeDTO.from_record(n, ancestry).model_dump())

    return {
        "sessions": [s.model_dump() for s in sessions],
        "nodes": node_dtos,
        "edges": [e.model_dump() for e in edges],
    }
