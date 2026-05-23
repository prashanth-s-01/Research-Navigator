import os
from pathlib import Path


class StorageService:
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_document_path(self, document_id: str) -> Path:
        return self.base_path / "pdfs" / f"{document_id}.pdf"

    def get_index_path(self, document_id: str) -> Path:
        return self.base_path / "indexes" / f"{document_id}.json"
