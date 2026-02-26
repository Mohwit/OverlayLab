from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.schemas import ResetResponseDTO

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset", response_model=ResetResponseDTO)
def reset_lab(container=Depends(get_container)):
    summary = container.graph_store.reset_graph()
    return ResetResponseDTO(
        cleared_nodes=summary["nodes"],
        cleared_sessions=summary["sessions"],
        message="Reset complete. All sessions, nodes, and file data were cleared.",
    )
