import logging
from fastapi import APIRouter, status

from models.schemas import QueryRequest, QueryResponse
from services.retrieval_service import RetrievalService
from utils.exception_handlers import BackendError

logger = logging.getLogger(__name__)

router = APIRouter()
retrieval_service = RetrievalService()


@router.post("/", response_model=QueryResponse, status_code=status.HTTP_200_OK)
async def query_document(request: QueryRequest) -> QueryResponse:
    """
    Query a document with a question.
    
    Args:
        request: Query request with document_id and question
        
    Returns:
        QueryResponse with answer, citations, and trace
    """
    if not request.document_id or not request.document_id.strip():
        logger.warning("Query attempt with missing document_id")
        raise BackendError(
            error_type="MISSING_DOCUMENT_ID",
            message="document_id is required.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if not request.question or not request.question.strip():
        logger.warning(f"Query attempt with empty question for document {request.document_id}")
        raise BackendError(
            error_type="MISSING_QUESTION",
            message="question is required and cannot be empty.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    logger.info(f"Processing query for document {request.document_id}: {request.question[:50]}...")

    result = await retrieval_service.retrieve(request.document_id, request.question)

    return QueryResponse(
        success=True,
        answer=result["answer"],
        citations=result.get("citations", []),
        trace=result.get("trace"),
    )
