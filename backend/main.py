from fastapi import FastAPI
from api.health import router as health_router
from api.upload import router as upload_router
from api.query import router as query_router
from config.settings import settings
from utils.logging_utils import configure_logging
from utils.exception_handlers import register_exception_handlers

configure_logging(settings)

app = FastAPI(
    title="Research Navigator API",
    description="Backend API for research paper indexing and question answering.",
    version="0.1.0",
)

app.include_router(health_router, prefix="", tags=["health"])
app.include_router(upload_router, prefix="/upload", tags=["upload"])
app.include_router(query_router, prefix="/query", tags=["query"])

register_exception_handlers(app)

@app.on_event("startup")
def startup_event() -> None:
    app.state.storage_path = settings.storage_path
