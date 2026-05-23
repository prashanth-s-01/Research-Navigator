import logging
import uuid
from fastapi import APIRouter, UploadFile, File, status, BackgroundTasks

from models.schemas import UploadResponse
from services.storage_service import StorageService
from services.indexing_service import IndexingService
from utils.file_utils import validate_pdf_file, save_uploaded_file
from utils.exception_handlers import BackendError
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()
storage_service = StorageService(settings.storage_path)
indexing_service = IndexingService(storage=storage_service)


@router.post("/pdf", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload a PDF file for document indexing.
    
    Args:
        file: PDF file to upload
        
    Returns:
        UploadResponse with document metadata
        
    Raises:
        BackendError: For validation or storage errors
    """
    if not file:
        logger.warning("Upload attempt with no file")
        raise BackendError(
            error_type="MISSING_FILE",
            message="No file provided in upload request.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    filename = file.filename or "unnamed.pdf"
    logger.info(f"Processing PDF upload: {filename}")

    try:
        file_data = await file.read()
    except Exception as exc:
        logger.error(f"Error reading uploaded file: {str(exc)}")
        raise BackendError(
            error_type="FILE_READ_ERROR",
            message="Failed to read the uploaded file.",
            detail=str(exc),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    validation_result = validate_pdf_file(file_data, filename)
    if not validation_result["is_valid"]:
        logger.warning(f"PDF validation failed: {validation_result['error_type']} - {validation_result['error_msg']}")
        raise BackendError(
            error_type=validation_result["error_type"],
            message=validation_result["error_msg"],
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    document_id = str(uuid.uuid4())
    document_path = storage_service.get_document_path(document_id)

    try:
        saved_path = save_uploaded_file(str(document_path), file_data)
        logger.info(f"PDF successfully saved: document_id={document_id}, path={saved_path}, size={len(file_data)} bytes")
    except Exception as exc:
        logger.error(f"Error saving PDF: {str(exc)}")
        raise BackendError(
            error_type="STORAGE_ERROR",
            message="Failed to save the PDF file.",
            detail=str(exc),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Schedule indexing in the background (non-blocking)
    background_tasks.add_task(self_or_index_task, document_id)

    return UploadResponse(
        document_id=document_id,
        filename=filename,
        status="uploaded",
        size_bytes=len(file_data),
        message="PDF uploaded successfully. Indexing scheduled.",
    )


def self_or_index_task(document_id: str) -> None:
    """Helper wrapper to call indexing service from BackgroundTasks (sync context)."""
    try:
        # IndexingService.build_index is async; run it in a new event loop
        import asyncio

        asyncio.run(indexing_service.build_index(document_id))
    except Exception:
        logger.exception("Background indexing task failed for document %s", document_id)
