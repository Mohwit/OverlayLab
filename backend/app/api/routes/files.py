from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.errors import AppError
from app.core.schemas import (
    FileContentResponse,
    FileDeleteRequest,
    FileDeleteResponse,
    FileEntryDTO,
    FilesResponse,
    LayerFilesResponse,
    FileWriteRequest,
    FileWriteResponse,
)
from app.services.sqlite_overlay import FileRecord

router = APIRouter(tags=["files"])


def _record_to_entry(record: FileRecord) -> FileEntryDTO:
    from datetime import datetime

    try:
        mtime = datetime.fromisoformat(record.created_at).timestamp()
    except (ValueError, TypeError):
        mtime = 0.0
    return FileEntryDTO(
        path=record.path,
        type="dir" if record.is_dir else "file",
        size=record.size,
        mtime=mtime,
    )


@router.get("/node/{node_id}/files", response_model=FilesResponse)
def get_node_files(node_id: str, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    entries = container.file_service.list_files(node_id)
    return FilesResponse(node_id=node_id, files=entries)


@router.get("/node/{node_id}/file", response_model=FileContentResponse)
def get_file_content(node_id: str, path: str, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    content = container.file_service.read_text_file(node_id, path)
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

    records = container.sqlite_overlay.list_layer_files(node_id, layer, index)
    files = [_record_to_entry(r) for r in records]
    return LayerFilesResponse(node_id=node_id, layer=layer, index=index, files=files)


@router.post("/node/{node_id}/file", response_model=FileWriteResponse)
def write_file(node_id: str, payload: FileWriteRequest, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    bytes_written = container.file_service.write_file(node_id, payload.path, payload.content, payload.mode)
    return FileWriteResponse(path=payload.path, bytes_written=bytes_written, node_id=node_id)


@router.delete("/node/{node_id}/file", response_model=FileDeleteResponse)
def delete_file(node_id: str, payload: FileDeleteRequest, container=Depends(get_container)):
    node = container.graph_store.get_node(node_id)
    if not node:
        raise AppError("NODE_NOT_FOUND", f"Node {node_id} was not found.", status_code=404)

    container.file_service.delete_file(node_id, payload.path)
    return FileDeleteResponse(path=payload.path, deleted=True)
