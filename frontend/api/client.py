import os
import requests
from requests.exceptions import RequestException

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

class BackendClientError(Exception):
    pass


def health_check() -> dict:
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        response.raise_for_status()
        return response.json()
    except RequestException as exc:
        raise BackendClientError(f"Unable to reach backend: {exc}")


def upload_pdf(file_path: str) -> dict:
    try:
        with open(file_path, "rb") as handle:
            response = requests.post(
                f"{BACKEND_URL}/upload/pdf",
                files={"file": (os.path.basename(file_path), handle, "application/pdf")},
                timeout=30,
            )
        response.raise_for_status()
        return response.json()
    except RequestException as exc:
        raise BackendClientError(f"Upload failed: {exc}")


def ask_question(document_id: str, question: str) -> dict:
    try:
        response = requests.post(
            f"{BACKEND_URL}/query/",
            json={"document_id": document_id, "question": question},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except RequestException as exc:
        raise BackendClientError(f"Query failed: {exc}")
