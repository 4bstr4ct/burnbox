from __future__ import annotations

import asyncio
import contextvars
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import httpx

from burnbox.exceptions import APIError, AuthExpiredError

logger = logging.getLogger(__name__)

T = TypeVar("T")

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY = 1.0
_DEFAULT_MAX_DELAY = 30.0
_DETAIL_MAX_LEN = 200

_RETRYABLE_STATUS = range(500, 600)
_RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.TimeoutException)


class RetryConfig:
    __slots__ = ("max_retries", "base_delay", "max_delay", "detail_max_len")

    def __init__(
        self,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_delay: float = _DEFAULT_BASE_DELAY,
        max_delay: float = _DEFAULT_MAX_DELAY,
        detail_max_len: int = _DETAIL_MAX_LEN,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.detail_max_len = detail_max_len


_attempt_var: contextvars.ContextVar[int] = contextvars.ContextVar("_attempt_var", default=1)


def _delay_for_attempt(attempt: int, cfg: RetryConfig) -> float:
    delay = float(min(cfg.base_delay * (2 ** (attempt - 1)), cfg.max_delay))
    return delay * random.uniform(0.5, 1.0)


class _Retryable(Exception):
    def __init__(self, delay: float) -> None:
        self.delay = delay


def raise_for_status(
    response: httpx.Response,
    cfg: RetryConfig | None = None,
) -> None:
    config = cfg or RetryConfig()
    attempt = _attempt_var.get(1)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 401:
            raise AuthExpiredError("Session expired") from exc
        detail = exc.response.text[: config.detail_max_len]
        if status_code in _RETRYABLE_STATUS and attempt < config.max_retries:
            delay = _delay_for_attempt(attempt, config)
            logger.warning(
                "Server error %d (attempt %d/%d), retrying in %.1fs",
                status_code,
                attempt,
                config.max_retries,
                delay,
            )
            raise _Retryable(delay)
        raise APIError(status_code=status_code, detail=detail) from exc


async def retry(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    cfg: RetryConfig | None = None,
    **kwargs: Any,
) -> T:
    config = cfg or RetryConfig()
    for attempt in range(1, config.max_retries + 1):
        token = _attempt_var.set(attempt)
        try:
            return await fn(*args, **kwargs)
        except _Retryable as r:
            await asyncio.sleep(r.delay)
            continue
        except _RETRYABLE_EXCEPTIONS as exc:
            if attempt < config.max_retries:
                delay = _delay_for_attempt(attempt, config)
                logger.warning(
                    "Request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt,
                    config.max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            else:
                raise APIError(status_code=0, detail=str(exc)) from exc
        except (APIError, AuthExpiredError):
            raise
        finally:
            _attempt_var.reset(token)
    raise APIError(status_code=0, detail="Max retries exceeded")
