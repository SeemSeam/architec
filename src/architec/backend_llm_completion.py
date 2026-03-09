from __future__ import annotations

import asyncio
import logging
from typing import Any

from .backend_llm_runtime import build_result
from .backend_llm_transport import (
    anthropic_messages_completion_fallback,
    litellm_completion,
    openai_chat_completion_fallback,
    openai_responses_completion_fallback,
)

logger = logging.getLogger("architec.backend_llm")

_RETRYABLE_HTTP_STATUS_CODES = {
    408,
    409,
    425,
    429,
    500,
    502,
    503,
    504,
    520,
    521,
    522,
    523,
    524,
}
_RETRYABLE_EXCEPTION_NAMES = {
    "ReadTimeout",
    "ConnectTimeout",
    "TimeoutException",
    "PoolTimeout",
    "ReadError",
    "WriteError",
    "ConnectError",
    "RemoteProtocolError",
}
_TRANSIENT_ERROR_HINTS = (
    "timed out",
    "timeout",
    "service unavailable",
    "temporarily unavailable",
    "bad gateway",
    "gateway timeout",
    "connection reset",
    "connection aborted",
    "connection refused",
    "broken pipe",
    "reconnecting",
    "too many requests",
    "rate limit",
)


def extract_http_status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def is_retryable_exception(exc: Exception) -> bool:
    if type(exc).__name__ in _RETRYABLE_EXCEPTION_NAMES:
        return True
    status = extract_http_status_code(exc)
    if isinstance(status, int) and status in _RETRYABLE_HTTP_STATUS_CODES:
        return True
    message = str(exc).lower()
    return any(hint in message for hint in _TRANSIENT_ERROR_HINTS)


def retry_timeout_schedule(timeout_sec: float, attempts: int = 3) -> list[float]:
    base = max(0.5, float(timeout_sec))
    if attempts <= 1:
        return [base]
    schedule = [base]
    for idx in range(1, attempts):
        schedule.append(max(base * (1.0 + idx), base + 8.0 * idx))
    return schedule


async def retry_backoff_sleep(attempt_idx: int) -> None:
    await asyncio.sleep(min(8.0, 0.8 * (2**attempt_idx)))


async def _complete_with_retry(
    *,
    request_name: str,
    call,
    provider_name: str,
    model: str,
    requested_model: str,
    timeout_sec: float,
    tier: str,
    required: bool,
) -> dict[str, Any] | None:
    timeouts = retry_timeout_schedule(timeout_sec, attempts=3)
    last_exc: Exception | None = None
    text = ""
    for idx, timeout_try in enumerate(timeouts):
        try:
            text = await call(timeout_try)
            if str(text or "").strip():
                break
            if idx < len(timeouts) - 1:
                await retry_backoff_sleep(idx)
                continue
        except Exception as exc:
            last_exc = exc
            if is_retryable_exception(exc) and idx < len(timeouts) - 1:
                await retry_backoff_sleep(idx)
                continue
            if required:
                from .backend_llm import BackendLLMUnavailableError

                raise BackendLLMUnavailableError(
                    f"backend llm {request_name} failed "
                    f"provider={provider_name} model={model} requested_model={requested_model} "
                    f"err_type={type(exc).__name__}: {exc!r}"
                ) from exc
            logger.warning(
                "%s failed provider=%s model=%s requested_model=%s err_type=%s err=%r",
                request_name,
                provider_name,
                model,
                requested_model,
                type(exc).__name__,
                exc,
            )
            return None

    if not str(text or "").strip():
        if required:
            from .backend_llm import BackendLLMUnavailableError

            if last_exc is not None:
                raise BackendLLMUnavailableError(
                    f"backend llm {request_name} failed after retries "
                    f"provider={provider_name} model={model} requested_model={requested_model} "
                    f"err_type={type(last_exc).__name__}: {last_exc!r}"
                ) from last_exc
            raise BackendLLMUnavailableError(
                f"backend llm {request_name} returned empty response "
                f"provider={provider_name} model={model} requested_model={requested_model}"
            )
        logger.warning(
            "%s returned empty text provider=%s model=%s requested_model=%s",
            request_name,
            provider_name,
            model,
            requested_model,
        )
        return None

    return build_result(
        text=text,
        model=model,
        requested_model=requested_model,
        tier=tier,
        provider=provider_name,
    )


async def complete_openai_chat(
    *,
    provider_cfg: dict[str, Any],
    provider_name: str,
    model: str,
    requested_model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout_sec: float,
    temperature: float,
    tier: str,
    required: bool = False,
) -> dict[str, Any] | None:
    return await _complete_with_retry(
        request_name="openai_chat",
        provider_name=provider_name,
        model=model,
        requested_model=requested_model,
        timeout_sec=timeout_sec,
        tier=tier,
        required=required,
        call=lambda timeout_try: openai_chat_completion_fallback(
            provider=provider_cfg,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout_try,
            temperature=temperature,
        ),
    )


async def complete_openai_responses(
    *,
    provider_cfg: dict[str, Any],
    provider_name: str,
    model: str,
    requested_model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout_sec: float,
    temperature: float,
    tier: str,
    required: bool = False,
) -> dict[str, Any] | None:
    return await _complete_with_retry(
        request_name="openai_responses",
        provider_name=provider_name,
        model=model,
        requested_model=requested_model,
        timeout_sec=timeout_sec,
        tier=tier,
        required=required,
        call=lambda timeout_try: openai_responses_completion_fallback(
            provider=provider_cfg,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout_try,
            temperature=temperature,
        ),
    )


async def complete_anthropic_messages(
    *,
    provider_cfg: dict[str, Any],
    provider_name: str,
    model: str,
    requested_model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout_sec: float,
    temperature: float,
    tier: str,
    required: bool = False,
) -> dict[str, Any] | None:
    return await _complete_with_retry(
        request_name="anthropic",
        provider_name=provider_name,
        model=model,
        requested_model=requested_model,
        timeout_sec=timeout_sec,
        tier=tier,
        required=required,
        call=lambda timeout_try: anthropic_messages_completion_fallback(
            provider=provider_cfg,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout_try,
            temperature=temperature,
        ),
    )


async def complete_litellm(
    *,
    provider_cfg: dict[str, Any],
    provider_name: str,
    model: str,
    requested_model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout_sec: float,
    temperature: float,
    tier: str,
    required: bool = False,
) -> dict[str, Any] | None:
    return await _complete_with_retry(
        request_name="litellm",
        provider_name=provider_name,
        model=model,
        requested_model=requested_model,
        timeout_sec=timeout_sec,
        tier=tier,
        required=required,
        call=lambda timeout_try: litellm_completion(
            provider=provider_cfg,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout_try,
            temperature=temperature,
        ),
    )
