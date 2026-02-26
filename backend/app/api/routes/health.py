from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.schemas import HealthPreflightDTO

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/preflight", response_model=HealthPreflightDTO)
def preflight(container=Depends(get_container)):
    return HealthPreflightDTO(**container.sqlite_overlay.preflight())
