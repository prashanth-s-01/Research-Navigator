from pydantic import BaseModel
from typing import List, Optional


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


class Citation(BaseModel):
    section: str
    page: Optional[int] = None


class QueryResponse(BaseModel):
    success: bool
    answer: str
    trace: List[str] = []
    citations: List[Citation] = []
