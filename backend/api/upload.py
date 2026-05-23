from fastapi import APIRouter, UploadFile, File, HTTPException
from models.schemas import UploadResponse
from services.storage_service import StorageService
from utils.file_utils import save_uploaded_file
from config.settings import settings
import uuid

router = APIRouter()
storage_service = StorageService(settings.storage_path)

@router.post("/pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    document_id = str(uuid.uuid4())
    document_path = storage_service.get_document_path(document_id)
    save_uploaded_file(str(document_path), await file.read())

    return UploadResponse(
        success=True,
        document_id=document_id,
        message="PDF uploaded successfully. Indexing will be generated in the next release.",
    )
