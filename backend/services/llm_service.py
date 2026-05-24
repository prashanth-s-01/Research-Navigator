import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

from config.settings import settings
from utils.exception_handlers import BackendError
from utils.retry_utils import retry_async

logger = logging.getLogger(__name__)


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        max_output_tokens: int,
        temperature: float,
        top_p: float,
        stop: Optional[List[str]] = None,
    ) -> str:
        raise NotImplementedError


class GroqProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str, timeout_seconds: int = 30):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://api.groq.com/openai/v1/responses"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        prompt: str,
        max_output_tokens: int,
        temperature: float,
        top_p: float,
        stop: Optional[List[str]] = None,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "input": prompt,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "top_p": top_p,
        }
        if stop:
            payload["stop"] = stop

        async def request_action() -> str:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                    response = await client.post(self.base_url, headers=self.headers, json=payload)
            except httpx.TimeoutException as exc:
                raise BackendError(
                    error_type="TIMEOUT",
                    message="Groq API request timed out.",
                    detail=str(exc),
                    status_code=504,
                )
            except httpx.RequestError as exc:
                raise BackendError(
                    error_type="PROVIDER_DOWNTIME",
                    message="Unable to reach Groq API.",
                    detail=str(exc),
                    status_code=503,
                )

            response_body = self._parse_response(response)
            return response_body

        def should_retry(exc: BaseException) -> bool:
            if isinstance(exc, BackendError):
                return exc.error_type in {"RATE_LIMIT", "TIMEOUT", "PROVIDER_DOWNTIME"}
            return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))

        return await retry_async(
            request_action,
            attempts=settings.groq_max_retries,
            delay_seconds=settings.groq_backoff_seconds,
            backoff_factor=2.0,
            should_retry=should_retry,
            logger=logger,
        )

    def _parse_response(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            raise BackendError(
                error_type="LLM_API_ERROR",
                message="Groq API returned an invalid JSON response.",
                detail=response.text,
                status_code=502,
            )

        if response.status_code == 401:
            raise BackendError(
                error_type="INVALID_API_KEY",
                message="Groq API key is invalid.",
                detail=json.dumps(payload, default=str),
                status_code=401,
            )

        if response.status_code == 429:
            raise BackendError(
                error_type="RATE_LIMIT",
                message="Groq API rate limit exceeded.",
                detail=json.dumps(payload, default=str),
                status_code=429,
            )

        if response.status_code in {413, 422}:
            raise BackendError(
                error_type="TOKEN_LIMIT_EXCEEDED",
                message="Groq API token limit was exceeded.",
                detail=json.dumps(payload, default=str),
                status_code=413,
            )

        if response.status_code >= 500:
            raise BackendError(
                error_type="PROVIDER_DOWNTIME",
                message="Groq API provider error occurred.",
                detail=json.dumps(payload, default=str),
                status_code=502,
            )

        if response.status_code != 200:
            error_message = payload.get("message") or payload.get("error") or response.text
            raise BackendError(
                error_type="LLM_API_ERROR",
                message=f"Groq API request failed: {error_message}",
                detail=json.dumps(payload, default=str),
                status_code=response.status_code,
            )

        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = payload.get("output") or payload.get("outputs")
        if isinstance(output, str) and output.strip():
            return output

        if isinstance(output, list):
            text_parts: List[str] = []
            for item in output:
                if isinstance(item, str):
                    text_parts.append(item)
                    continue
                if not isinstance(item, dict):
                    continue

                text = item.get("text")
                if isinstance(text, str):
                    text_parts.append(text)

                content = item.get("content")
                if isinstance(content, str):
                    text_parts.append(content)
                elif isinstance(content, list):
                    for content_item in content:
                        if isinstance(content_item, str):
                            text_parts.append(content_item)
                        elif isinstance(content_item, dict):
                            nested_text = content_item.get("text")
                            if isinstance(nested_text, str):
                                text_parts.append(nested_text)

            combined_output = "\n".join(part.strip() for part in text_parts if part and part.strip())
            if combined_output:
                return combined_output

        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                message = first_choice.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        return content
                return str(first_choice.get("content") or first_choice.get("text") or "")
            return str(first_choice)

        raise BackendError(
            error_type="LLM_API_ERROR",
            message="Groq API returned an unexpected payload format.",
            detail=json.dumps(payload, default=str),
            status_code=502,
        )


class LLMService:
    def __init__(
        self,
        api_key: str,
        model_name: str,
        provider: Optional[BaseLLMProvider] = None,
    ):
        self.provider = provider or GroqProvider(
            api_key=api_key,
            model_name=model_name,
            timeout_seconds=settings.groq_timeout_seconds,
        )

    async def generate(
        self,
        prompt: str,
        max_output_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop: Optional[List[str]] = None,
    ) -> str:
        return await self.provider.generate(
            prompt=prompt,
            max_output_tokens=max_output_tokens or settings.groq_max_output_tokens,
            temperature=temperature if temperature is not None else settings.groq_temperature,
            top_p=top_p if top_p is not None else settings.groq_top_p,
            stop=stop,
        )
