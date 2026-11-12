from __future__ import annotations

from fastapi import APIRouter

from src.controllers import health_controller
from src.schemas.common import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> dict:
    return health_controller.health()
