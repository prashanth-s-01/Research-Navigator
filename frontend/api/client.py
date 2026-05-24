import json
import os
from typing import Optional

import requests
from requests.exceptions import RequestException

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class BackendClientError(Exception):
    def __init__(self, message: str, error_type: Optional[str] = None):
        super().__init__(message)
        self.error_type = error_type


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


def _parse_error_response(response: requests.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {"message": response.text}


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
        error_type = None
        message = str(exc)
        response = getattr(exc, "response", None)
        if response is not None:
            payload = _parse_error_response(response)
            message = payload.get("message", message)
            error_type = payload.get("error_type")
        raise BackendClientError(f"Query failed: {message}", error_type=error_type)
