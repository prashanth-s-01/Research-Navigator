import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from pageindex import PageIndexAPIError, PageIndexClient

from services.storage_service import StorageService
from config.settings import settings
from utils.exception_handlers import BackendError

logger = logging.getLogger(__name__)


class IndexingService:
    """Index documents with PageIndex and persist traversal artifacts."""

    def __init__(self, storage: Optional[StorageService] = None, client: Optional[PageIndexClient] = None):
        self.storage = storage or StorageService(settings.storage_path)
        self.client = client or PageIndexClient(settings.pageindex_api_key)

    async def build_index(self, document_id: str) -> Dict[str, Any]:
        """Asynchronously build a PageIndex index for a document."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._build_index_sync, document_id)

    def _build_index_sync(self, document_id: str) -> Dict[str, Any]:
        index_dir = self.storage.ensure_index_dir(document_id)
        status_path = index_dir / "status.json"

        def write_status(state: str, detail: Optional[str] = None) -> None:
            payload = {
                "state": state,
                "detail": detail,
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
            try:
                index_dir.mkdir(parents=True, exist_ok=True)
                status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            except Exception:
                logger.exception("Failed to write status.json")

        write_status("running")

        pdf_path = self.storage.get_document_path(document_id)
        if not pdf_path.exists():
            write_status("failed", "source PDF not found")
            raise BackendError(
                error_type="DOCUMENT_NOT_FOUND",
                message="Source PDF not found in storage.",
                detail=str(pdf_path),
            )

        try:
            submission = self.client.submit_document(str(pdf_path), mode=settings.pageindex_mode)
            pageindex_doc_id = submission.get("doc_id")
            if not pageindex_doc_id:
                raise ValueError("PageIndex submit_document returned no doc_id.")
        except PageIndexAPIError as exc:
            write_status("failed", "pageindex submission failed")
            logger.exception("PageIndex document submission failed")
            raise BackendError(
                error_type="PAGEINDEX_SUBMISSION_FAILED",
                message="Failed to submit document to PageIndex.",
                detail=str(exc),
            )
        except Exception as exc:
            write_status("failed", "pageindex submission error")
            logger.exception("Unexpected error during PageIndex document submission")
            raise BackendError(
                error_type="PAGEINDEX_SUBMISSION_ERROR",
                message="An unexpected error occurred while submitting the document to PageIndex.",
                detail=str(exc),
            )

        try:
            tree_response = self._wait_for_tree(pageindex_doc_id)
        except BackendError as exc:
            write_status("failed", exc.detail or exc.message)
            raise
        except Exception as exc:
            write_status("failed", "tree generation error")
            logger.exception("Unexpected error while waiting for PageIndex tree")
            raise BackendError(
                error_type="PAGEINDEX_TREE_ERROR",
                message="Failed to generate PageIndex tree.",
                detail=str(exc),
            )

        tree = tree_response.get("tree") if isinstance(tree_response, dict) else tree_response
        metadata = {
            "document_id": document_id,
            "pageindex_doc_id": pageindex_doc_id,
            "pageindex_status": tree_response.get("status") if isinstance(tree_response, dict) else None,
            "retrieval_ready": tree_response.get("retrieval_ready") if isinstance(tree_response, dict) else None,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        summaries = self._extract_summaries(tree)

        try:
            (index_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
            (index_dir / "tree.json").write_text(json.dumps(tree, ensure_ascii=False, indent=2))
            (index_dir / "summaries.json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2))
            (index_dir / "raw_tree.json").write_text(json.dumps(tree_response, ensure_ascii=False, indent=2))
        except Exception as exc:
            write_status("failed", "serialization error")
            logger.exception("Failed to persist PageIndex artifacts")
            raise BackendError(
                error_type="SERIALIZATION_ERROR",
                message="Failed to persist PageIndex artifacts.",
                detail=str(exc),
            )

        write_status("complete")
        logger.info(f"Index built for document {document_id}: pageindex_doc_id={pageindex_doc_id}")

        return {"metadata": metadata, "tree": tree, "summaries": summaries}

    def _wait_for_tree(self, pageindex_doc_id: str) -> Dict[str, Any]:
        attempts = 0
        last_status = None
        while attempts < settings.pageindex_poll_attempts:
            try:
                response = self.client.get_tree(pageindex_doc_id, node_summary=True)
            except PageIndexAPIError as exc:
                logger.warning("PageIndex get_tree attempt %s failed: %s", attempts + 1, exc)
                if attempts + 1 >= settings.pageindex_poll_attempts:
                    raise BackendError(
                        error_type="PAGEINDEX_TREE_TIMEOUT",
                        message="PageIndex tree generation timed out.",
                        detail=str(exc),
                    )
                time.sleep(settings.pageindex_poll_interval_seconds)
                attempts += 1
                continue

            status = response.get("status") if isinstance(response, dict) else None
            last_status = status
            retrieval_ready = response.get("retrieval_ready") if isinstance(response, dict) else None
            tree = response.get("tree") if isinstance(response, dict) else response

            if status in ("completed", "success") or retrieval_ready:
                return response

            keys = sorted(response.keys()) if isinstance(response, dict) else None
            logger.info("Waiting for PageIndex tree: attempt %s status=%s keys=%s", attempts + 1, status, keys)
            time.sleep(settings.pageindex_poll_interval_seconds)
            attempts += 1

        raise BackendError(
            error_type="PAGEINDEX_TREE_TIMEOUT",
            message="PageIndex tree generation did not complete in time.",
            detail=f"Last PageIndex status: {last_status}",
        )

    def _extract_summaries(self, node: Any) -> Dict[str, str]:
        summaries: Dict[str, str] = {}

        def walk(current: Any) -> None:
            if isinstance(current, dict):
                node_id = current.get("id")
                summary = current.get("summary") or current.get("node_summary") or current.get("title")
                if node_id and isinstance(summary, str):
                    summaries[node_id] = summary
                for child in current.get("children", []) or current.get("child_nodes", []) or []:
                    walk(child)
            elif isinstance(current, list):
                for item in current:
                    walk(item)

        walk(node)
        return summaries
