from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
from models.schemas import ApiError


class BackendError(Exception):
    def __init__(self, error_type: str, message: str, detail: str | None = None):
        self.error_type = error_type
        self.message = message
        self.detail = detail


def register_exception_handlers(app) -> None:
    @app.exception_handler(BackendError)
    async def backend_error_handler(request: Request, exc: BackendError):
        payload = ApiError(
            error_type=exc.error_type,
            message=exc.message,
            detail=exc.detail,
        )
        return JSONResponse(status_code=HTTP_400_BAD_REQUEST, content=payload.dict())

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        payload = ApiError(
            error_type="HTTP_ERROR",
            message=exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred.",
            detail=str(exc.status_code),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.dict())

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        payload = ApiError(
            error_type="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred.",
            detail=str(exc),
        )
        return JSONResponse(status_code=HTTP_500_INTERNAL_SERVER_ERROR, content=payload.dict())
