from pydantic import BaseModel
from typing import Optional


class ApiError(BaseModel):
    error: bool = True
    error_type: str
    message: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str = "uploaded"
    size_bytes: int
    message: Optional[str] = None


class QueryRequest(BaseModel):
    document_id: str
    question: str


class QueryResponse(BaseModel):
    success: bool
    answer: str
    citations: list[str] = []
    trace: Optional[str] = None
