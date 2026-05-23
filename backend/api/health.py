import logging
from fastapi import APIRouter, status

from models.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
async def health() -> HealthResponse:
    """Check backend health status."""
    return HealthResponse(status="ok", version="0.1.0")
