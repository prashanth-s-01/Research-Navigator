from fastapi import APIRouter, HTTPException
from models.schemas import QueryRequest, QueryResponse
from services.retrieval_service import RetrievalService

router = APIRouter()
retrieval_service = RetrievalService()

@router.post("/", response_model=QueryResponse)
def query_document(request: QueryRequest) -> QueryResponse:
    if not request.document_id or not request.question.strip():
        raise HTTPException(status_code=400, detail="document_id and question are required.")

    result = retrieval_service.retrieve(request.document_id, request.question)
    return QueryResponse(
        success=True,
        answer=result["answer"],
        citations=result["citations"],
        trace=result["trace"],
    )
