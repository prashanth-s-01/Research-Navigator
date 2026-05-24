import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from pageindex import PageIndexAPIError, PageIndexClient

from services.llm_service import LLMService
from services.prompt_utils import (
    build_groq_prompt,
    extract_retrieval_snippets,
)
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
        retrieved_nodes = self._extract_retrieved_nodes(retrieval_result)
        if not retrieved_nodes:
            raise BackendError(
                error_type="EMPTY_RETRIEVAL",
                message="No relevant document sections were found for this query.",
                detail=json.dumps(retrieval_result, default=str),
                status_code=404,
            )

        citations = self._extract_citations(retrieved_nodes)
        trace = self._extract_trace(retrieved_nodes)
        snippets = extract_retrieval_snippets(retrieval_result)
        prompt = build_groq_prompt(
            question=question,
            snippets=snippets,
            trace=trace,
            citations=citations,
        )

        answer = await self.llm_service.generate(
            prompt=prompt,
            max_output_tokens=settings.groq_max_output_tokens,
            temperature=settings.groq_temperature,
            top_p=settings.groq_top_p,
        )

        return {
            "answer": answer.strip() or "No answer could be generated from the retrieved context.",
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

    def _extract_retrieved_nodes(self, retrieval: Dict[str, Any]) -> List[Dict[str, Any]]:
        retrieved_nodes = retrieval.get("retrieved_nodes")
        if isinstance(retrieved_nodes, list):
            return [node for node in retrieved_nodes if isinstance(node, dict)]

        node = retrieval.get("retrieval")
        if isinstance(node, dict) and isinstance(node.get("retrieved_nodes"), list):
            return [item for item in node.get("retrieved_nodes") if isinstance(item, dict)]

        return []

    def _extract_citations(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        citations: List[Dict[str, Any]] = []
        seen: set = set()

        for node in nodes:
            section = node.get("title") or node.get("section_title") or str(node.get("id", "Unknown"))
            page = self._parse_page_number(node)
            citation = {"section": str(section), "page": page}
            citation_key = (section, page)
            if citation_key not in seen:
                citations.append(citation)
                seen.add(citation_key)

        return citations

    def _extract_trace(self, nodes: List[Dict[str, Any]]) -> List[str]:
        trace: List[str] = []
        for node in nodes:
            title = node.get("title") or node.get("section_title") or str(node.get("id", "Unknown"))
            if isinstance(title, str) and title.strip():
                trace.append(title.strip())
                continue

            relevant_contents = node.get("relevant_contents")
            if isinstance(relevant_contents, list):
                for group in relevant_contents:
                    items = group if isinstance(group, list) else [group]
                    for item in items:
                        if isinstance(item, dict) and item.get("section_title"):
                            trace.append(str(item["section_title"]).strip())

        return [part for part in trace if part]

    def _parse_page_number(self, node: Dict[str, Any]) -> Optional[int]:
        page_value = None
        if isinstance(node.get("physical_index"), str):
            page_value = node["physical_index"]
        elif isinstance(node.get("page"), (str, int)):
            page_value = node.get("page")

        if isinstance(page_value, int):
            return page_value
        if isinstance(page_value, str):
            match = re.search(r"(\d+)", page_value)
            if match:
                return int(match.group(1))

        metadata = node.get("metadata")
        if isinstance(metadata, list):
            for value in metadata:
                if isinstance(value, str):
                    match = re.search(r"(\d+)", value)
                    if match:
                        return int(match.group(1))

        return None
