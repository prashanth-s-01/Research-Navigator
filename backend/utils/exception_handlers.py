import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from models.schemas import ApiError

logger = logging.getLogger(__name__)


def register_exception_handlers(app) -> None:
    """Register global exception handlers for the FastAPI app."""

    @app.exception_handler(BackendError)
    async def backend_error_handler(request: Request, exc: BackendError):
        logger.warning(f"Backend error: {exc.error_type} - {exc.message}")
        payload = ApiError(
            error_type=exc.error_type,
            message=exc.message,
            detail=exc.detail,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        payload = ApiError(
            error_type="HTTP_ERROR",
            message=exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred.",
            detail=str(exc.status_code),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}", exc_info=True)
        payload = ApiError(
            error_type="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred.",
            detail=str(exc) if app.debug else None,
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())


class BackendError(Exception):
    """Custom exception for backend-specific errors."""

    def __init__(
        self,
        error_type: str,
        message: str,
        detail: Optional[str] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        self.error_type = error_type
        self.message = message
        self.detail = detail
        self.status_code = status_code
