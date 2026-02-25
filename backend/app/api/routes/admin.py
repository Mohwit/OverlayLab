from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.schemas import ResetResponseDTO

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset", response_model=ResetResponseDTO)
def reset_lab(container=Depends(get_container)):
    for node in container.graph_store.get_all_nodes():
        try:
            container.overlay_manager.unmount_path(node.merged)
        except Exception:
            continue

    container.overlay_manager.startup_cleanup_orphan_mounts(set())
    summary = container.graph_store.reset_graph()
    container.overlay_manager.clear_access_cache()

    return ResetResponseDTO(
        cleared_nodes=summary["nodes"],
        cleared_sessions=summary["sessions"],
        message="Reset complete. Session metadata and local overlay node files were removed.",
    )
