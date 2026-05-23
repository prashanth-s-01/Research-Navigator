import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing PDF storage and index organization."""

    def __init__(self, base_path: str):
        """
        Initialize storage service.
        
        Args:
            base_path: Base directory for all storage
        """
        self.base_path = Path(base_path)
        self.pdfs_dir = self.base_path / "pdfs"
        self.indexes_dir = self.base_path / "indexes"
        
        self.pdfs_dir.mkdir(parents=True, exist_ok=True)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage service initialized at {self.base_path}")

    def get_document_path(self, document_id: str) -> Path:
        """Get the file path for a document PDF."""
        return self.pdfs_dir / f"{document_id}.pdf"

    def get_index_path(self, document_id: str) -> Path:
        """Get the file path for a document index."""
        return self.indexes_dir / f"{document_id}.json"

    def document_exists(self, document_id: str) -> bool:
        """Check if a document exists in storage."""
        return self.get_document_path(document_id).exists()

    def get_document_size(self, document_id: str) -> int:
        """Get the size of a document in bytes."""
        doc_path = self.get_document_path(document_id)
        if not doc_path.exists():
            return 0
        return doc_path.stat().st_size
