import os
from typing import Any, Dict, Optional

import requests
from requests.exceptions import RequestException, Timeout

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class BackendClientError(Exception):
    def __init__(self, message: str, error_type: Optional[str] = None):
        super().__init__(message)
        self.error_type = error_type


def _build_url(path: str) -> str:
    return f"{BACKEND_URL.rstrip('/')}{path}"


def _parse_error_response(response: requests.Response) -> Dict[str, Optional[str]]:
    try:
        payload = response.json()
        return {
            "message": payload.get("message") if isinstance(payload, dict) else response.text,
            "error_type": payload.get("error_type") if isinstance(payload, dict) else None,
        }
    except ValueError:
        return {"message": response.text, "error_type": None}


def _raise_request_error(exc: RequestException) -> None:
    error_type = None
    message = str(exc)
    response = getattr(exc, "response", None)

    if isinstance(exc, Timeout):
        error_type = "TIMEOUT"
        message = "The request timed out. Please try again."
    elif response is not None:
        parsed = _parse_error_response(response)
        message = parsed.get("message") or message
        error_type = parsed.get("error_type")

    raise BackendClientError(message, error_type=error_type)


def health_check() -> Dict[str, Any]:
    try:
        response = requests.get(_build_url("/health"), timeout=10)
        response.raise_for_status()
        return response.json()
    except RequestException as exc:
        _raise_request_error(exc)


def upload_pdf(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, "rb") as handle:
            response = requests.post(
                _build_url("/upload/pdf"),
                files={"file": (os.path.basename(file_path), handle, "application/pdf")},
                timeout=60,
            )
        response.raise_for_status()
        return response.json()
    except RequestException as exc:
        _raise_request_error(exc)


def ask_question(document_id: str, question: str) -> Dict[str, Any]:
    try:
        response = requests.post(
            _build_url("/query/"),
            json={"document_id": document_id, "question": question},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except RequestException as exc:
        _raise_request_error(exc)
