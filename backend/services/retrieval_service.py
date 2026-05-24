import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from pageindex import PageIndexAPIError, PageIndexClient

from services.llm_service import LLMService
from services.prompt_utils import build_groq_prompt, extract_retrieval_snippets
from services.storage_service import StorageService
from config.settings import settings
from utils.exception_handlers import BackendError

logger = logging.getLogger(__name__)


class RetrievalService:
    """Retrieve answers from PageIndex and use Groq to generate a final response."""

    def __init__(
        self,
        storage: Optional[StorageService] = None,
        client: Optional[PageIndexClient] = None,
        llm_service: Optional[LLMService] = None,
    ):
        self.storage = storage or StorageService(settings.storage_path)
        self.client = client or PageIndexClient(settings.pageindex_api_key)
        self.llm_service = llm_service or LLMService(
            api_key=settings.groq_api_key,
            model_name=settings.groq_model,
        )

    async def retrieve(self, document_id: str, question: str) -> dict:
        metadata = self._load_metadata(document_id)
        pageindex_doc_id = metadata.get("pageindex_doc_id")

        if not pageindex_doc_id:
            raise BackendError(
                error_type="INDEX_NOT_AVAILABLE",
                message="No PageIndex document identifier found for this document.",
                detail="metadata.json missing pageindex_doc_id",
            )

        submission = await asyncio.to_thread(self._submit_query, pageindex_doc_id, question)
        retrieval_id = self._extract_retrieval_id(submission)
        if not retrieval_id:
            raise BackendError(
                error_type="PAGEINDEX_RESPONSE_INVALID",
                message="PageIndex did not return a retrieval identifier.",
                detail=json.dumps(submission, default=str),
            )

        retrieval_result = await asyncio.to_thread(self._wait_for_retrieval, retrieval_id)
        citations = self._extract_citations(retrieval_result)
        trace = self._extract_trace(retrieval_result)
        snippets = extract_retrieval_snippets(retrieval_result)
        prompt = build_groq_prompt(question, snippets, citations)

        answer = await self.llm_service.generate(
            prompt=prompt,
            max_output_tokens=settings.groq_max_output_tokens,
            temperature=settings.groq_temperature,
            top_p=settings.groq_top_p,
        )

        return {
            "answer": answer.strip(),
            "citations": citations,
            "trace": trace,
        }

    def _submit_query(self, pageindex_doc_id: str, question: str) -> Dict[str, Any]:
        try:
            return self.client.submit_query(pageindex_doc_id, question, thinking=True)
        except PageIndexAPIError as exc:
            logger.exception("PageIndex submit_query failed")
            raise BackendError(
                error_type="PAGEINDEX_RETRIEVAL_FAILED",
                message="Failed to submit query to PageIndex.",
                detail=str(exc),
            )

    def _load_metadata(self, document_id: str) -> Dict[str, Any]:
        index_dir = self.storage.get_index_dir(document_id)
        metadata_path = index_dir / "metadata.json"
        if not metadata_path.exists():
            raise BackendError(
                error_type="METADATA_NOT_FOUND",
                message="Index metadata not found for this document.",
                detail=str(metadata_path),
            )

        try:
            return json.loads(metadata_path.read_text())
        except Exception as exc:
            logger.exception("Failed to read metadata.json")
            raise BackendError(
                error_type="METADATA_READ_ERROR",
                message="Failed to read index metadata.",
                detail=str(exc),
            )

    def _extract_retrieval_id(self, submission: Dict[str, Any]) -> Optional[str]:
        return submission.get("retrieval_id") or submission.get("id")

    def _wait_for_retrieval(self, retrieval_id: str) -> Dict[str, Any]:
        attempts = 0
        while attempts < settings.pageindex_poll_attempts:
            try:
                retrieval = self.client.get_retrieval(retrieval_id)
            except PageIndexAPIError as exc:
                logger.warning("PageIndex get_retrieval attempt %s failed: %s", attempts + 1, exc)
                if attempts + 1 >= settings.pageindex_poll_attempts:
                    raise BackendError(
                        error_type="PAGEINDEX_RETRIEVAL_TIMEOUT",
                        message="Retrieval polling timed out.",
                        detail=str(exc),
                    )
                time.sleep(settings.pageindex_poll_interval_seconds)
                attempts += 1
                continue

            status = retrieval.get("status")
            if status in ("completed", "done", "success"):
                return retrieval
            if status in ("failed", "error"):
                raise BackendError(
                    error_type="PAGEINDEX_RETRIEVAL_FAILED",
                    message="PageIndex retrieval failed.",
                    detail=json.dumps(retrieval, default=str),
                )

            logger.info("Waiting for PageIndex retrieval: attempt %s status=%s", attempts + 1, status)
            time.sleep(settings.pageindex_poll_interval_seconds)
            attempts += 1

        raise BackendError(
            error_type="PAGEINDEX_RETRIEVAL_TIMEOUT",
            message="PageIndex retrieval did not complete in time.",
        )

    def _extract_citations(self, retrieval: Dict[str, Any]) -> List[str]:
        citations = []
        if retrieval.get("citations"):
            citations = retrieval["citations"]
        elif retrieval.get("sources"):
            citations = retrieval["sources"]
        elif retrieval.get("references"):
            citations = retrieval["references"]

        if isinstance(citations, list):
            extracted = [str(item) for item in citations]
        elif citations:
            extracted = [str(citations)]
        else:
            extracted = []

        retrieved_nodes = retrieval.get("retrieved_nodes")
        if isinstance(retrieved_nodes, list):
            for node in retrieved_nodes:
                if not isinstance(node, dict):
                    continue
                node_id = node.get("id")
                title = node.get("title")
                if title and node_id:
                    extracted.append(f"{title} ({node_id})")
                elif title:
                    extracted.append(str(title))
                elif node_id:
                    extracted.append(str(node_id))

        return list(dict.fromkeys(item for item in extracted if item))

    def _extract_trace(self, retrieval: Dict[str, Any]) -> str:
        trace_value = retrieval.get("trace") or retrieval.get("debug") or retrieval.get("details")
        if isinstance(trace_value, str):
            return trace_value
        return json.dumps(retrieval, ensure_ascii=False, indent=2)
