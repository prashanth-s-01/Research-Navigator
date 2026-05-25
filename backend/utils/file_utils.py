import os
import logging
from pathlib import Path

from config.settings import settings

logger = logging.getLogger(__name__)

PDF_MAGIC_BYTES = b"%PDF"
MIN_PDF_SIZE = 100
MAX_PDF_SIZE = settings.max_upload_size_mb * 1024 * 1024


def validate_pdf_file(file_data: bytes, filename: str) -> dict:
    """
    Validate PDF file format and size.
    
    Args:
        file_data: Raw file bytes
        filename: Original filename
        
    Returns:
        dict with is_valid (bool) and error_msg (str or None)
    """
    if not filename.lower().endswith(".pdf"):
        return {
            "is_valid": False,
            "error_msg": f"Invalid file extension: {filename}. Only .pdf files are accepted.",
            "error_type": "INVALID_FILE_TYPE"
        }

    if len(file_data) == 0:
        return {
            "is_valid": False,
            "error_msg": "Uploaded file is empty.",
            "error_type": "EMPTY_FILE"
        }

    if len(file_data) < MIN_PDF_SIZE:
        return {
            "is_valid": False,
            "error_msg": f"File is too small ({len(file_data)} bytes). PDFs must be at least {MIN_PDF_SIZE} bytes.",
            "error_type": "FILE_TOO_SMALL"
        }

    if len(file_data) > MAX_PDF_SIZE:
        return {
            "is_valid": False,
            "error_msg": (
                f"File is too large ({len(file_data) / 1024 / 1024:.1f} MB). "
                f"Maximum size is {settings.max_upload_size_mb} MB."
            ),
            "error_type": "FILE_TOO_LARGE"
        }

    if not file_data.startswith(PDF_MAGIC_BYTES):
        logger.warning(f"File {filename} does not have PDF magic bytes")
        return {
            "is_valid": False,
            "error_msg": f"File does not appear to be a valid PDF. Invalid file signature.",
            "error_type": "INVALID_PDF_FORMAT"
        }

    return {"is_valid": True, "error_msg": None, "error_type": None}


def ensure_directory(path: str | Path) -> None:
    """Create directory and all parent directories as needed."""
    Path(path).mkdir(parents=True, exist_ok=True)


def save_uploaded_file(upload_path: str | Path, file_data: bytes) -> Path:
    """
    Save uploaded file to disk.
    
    Args:
        upload_path: Target file path
        file_data: Raw file bytes
        
    Returns:
        Path object of saved file
    """
    upload_path = Path(upload_path)
    ensure_directory(upload_path.parent)
    upload_path.write_bytes(file_data)
    logger.info(f"File saved to {upload_path}, size: {len(file_data)} bytes")
    return upload_path
