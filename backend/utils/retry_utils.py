import asyncio
import logging
from typing import Awaitable, Callable, Optional, Type, TypeVar

T = TypeVar("T")

RetryPredicate = Callable[[BaseException], bool]


def default_retry_predicate(exc: BaseException) -> bool:
    return isinstance(exc, (asyncio.TimeoutError,))


async def retry_async(
    action: Callable[[], Awaitable[T]],
    attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    should_retry: Optional[RetryPredicate] = None,
    logger: Optional[logging.Logger] = None,
) -> T:
    logger = logger or logging.getLogger(__name__)
    should_retry = should_retry or default_retry_predicate

    attempt = 0
    current_delay = delay_seconds

    while True:
        try:
            return await action()
        except Exception as exc:
            attempt += 1
            retryable = should_retry(exc)
            if attempt > attempts or not retryable:
                logger.debug("Not retrying after attempt %s: %s", attempt, exc)
                raise

            logger.warning(
                "Retryable error on attempt %s/%s: %s. Sleeping %.1fs before retrying.",
                attempt,
                attempts,
                exc,
                current_delay,
            )
            await asyncio.sleep(current_delay)
            current_delay *= backoff_factor
