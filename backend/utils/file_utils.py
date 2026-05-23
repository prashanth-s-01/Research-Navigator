import os
from pathlib import Path


def ensure_directory(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def save_uploaded_file(upload_path: str, file_data: bytes) -> str:
    ensure_directory(os.path.dirname(upload_path))
    with open(upload_path, "wb") as handle:
        handle.write(file_data)
    return upload_path
