from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.errors import AppError
from app.core.schemas import DiffDTO

router = APIRouter(tags=["diff"])


@router.get("/diff", response_model=DiffDTO)
def diff_nodes(from_node_id: str, to_node_id: str, container=Depends(get_container)):
    from_node = container.graph_store.get_node(from_node_id)
    to_node = container.graph_store.get_node(to_node_id)

    if not from_node or not to_node:
        raise AppError("NODE_NOT_FOUND", "One or both nodes were not found.", status_code=404)

    container.overlay_manager.mount_node(from_node)
    container.overlay_manager.mount_node(to_node)

    if from_node.mount_state != "mounted":
        from_node.mount_state = "mounted"
        container.graph_store.update_node(from_node)
    if to_node.mount_state != "mounted":
        to_node.mount_state = "mounted"
        container.graph_store.update_node(to_node)

    return container.file_service.diff_nodes(from_node, to_node)
