from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.errors import AppError
from app.core.schemas import (
    FileContentResponse,
    FileDeleteRequest,
    FileDeleteResponse,
    FilesResponse,
    LayerFilesResponse,
    FileWriteRequest,
    FileWriteResponse,
)

router = APIRouter(tags=["files"])


@router.get("/node/{node_id}/files", response_model=FilesResponse)
def get_node_files(node_id: str, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    container.overlay_manager.mount_node(node)
    if node.mount_state != "mounted":
        node.mount_state = "mounted"
        container.graph_store.update_node(node)

    entries = container.file_service.list_files(node)
    return FilesResponse(node_id=node_id, files=entries)


@router.get("/node/{node_id}/file", response_model=FileContentResponse)
def get_file_content(node_id: str, path: str, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    container.overlay_manager.mount_node(node)
    if node.mount_state != "mounted":
        node.mount_state = "mounted"
        container.graph_store.update_node(node)

    content = container.file_service.read_text_file(node, path)
    return FileContentResponse(node_id=node_id, path=path, content=content)


@router.get("/node/{node_id}/layer-files", response_model=LayerFilesResponse)
def get_layer_files(
    node_id: str,
    layer: Literal["merged", "upper", "lower"],
    index: int | None = None,
    container=Depends(get_container),
):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    if layer == "merged":
        container.overlay_manager.mount_node(node)
        if node.mount_state != "mounted":
            node.mount_state = "mounted"
            container.graph_store.update_node(node)
        root = Path(node.merged)
    elif layer == "upper":
        root = Path(node.upperdir)
    else:
        if index is None:
            raise AppError("INVALID_FILE_PATH", "Lowerdir index is required for lower layer inspection.", status_code=400)
        if index < 0 or index >= len(node.lowerdirs):
            raise AppError("INVALID_FILE_PATH", "Lowerdir index out of range.", status_code=400)
        root = Path(node.lowerdirs[index])

    files = container.file_service.list_files_from_root(root)
    return LayerFilesResponse(node_id=node_id, layer=layer, index=index, files=files)


@router.post("/node/{node_id}/file", response_model=FileWriteResponse)
def write_file(node_id: str, payload: FileWriteRequest, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    container.overlay_manager.mount_node(node)
    node.mount_state = "mounted"
    container.graph_store.update_node(node)

    bytes_written = container.file_service.write_file(node, payload.path, payload.content, payload.mode)
    container.overlay_manager.touch(node_id)
    return FileWriteResponse(path=payload.path, bytes_written=bytes_written, node_id=node_id)


@router.delete("/node/{node_id}/file", response_model=FileDeleteResponse)
def delete_file(node_id: str, payload: FileDeleteRequest, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    container.overlay_manager.mount_node(node)
    node.mount_state = "mounted"
    container.graph_store.update_node(node)

    container.file_service.delete_file(node, payload.path)
    container.overlay_manager.touch(node_id)
    return FileDeleteResponse(path=payload.path, deleted=True)
