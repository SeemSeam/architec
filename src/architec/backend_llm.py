from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from .backend_llm_architect_config import (
    ArchitectLLMCandidate,
    load_architect_backend_llm_config,
    resolve_architect_candidates,
)
from .backend_llm_cache import load_cached_result, save_cached_result
from .backend_llm_candidate_chain import run_candidate_chain
from .backend_llm_completion import (
    _complete_with_retry,
    complete_anthropic_messages,
    complete_litellm,
    complete_openai_chat,
    complete_openai_responses,
    extract_http_status_code,
    is_retryable_exception,
    retry_backoff_sleep,
    retry_timeout_schedule,
)
from .backend_llm_config import (
    BackendLLMConfig,
    apply_model_map,
    choose_model,
    load_backend_llm_config,
    normalize_model_name,
    prefers_anthropic_messages,
    prefers_openai_chat,
    prefers_openai_responses,
    resolve_temperature,
)
from .backend_llm_context import resolve_runtime_context_strict
from .backend_llm_errors import (
    BackendLLMError,
    BackendLLMResponseError,
    BackendLLMUnavailableError,
)
from .backend_llm_failover import (
    FailoverPolicy,
    record_parse_failure,
    record_success,
    record_transport_failure,
)
from .backend_llm_json_helpers import (
    process_json_attempt,
    resolve_provider_hint_context,
)
from .backend_llm_runtime import (
    build_gateway_proxy_provider,
    build_messages_for_candidate,
    build_result,
    legacy_failover_policy,
    provider_attempt_chain,
)
from .resource_paths import resolve_architect_llm_config_file
from .backend_llm_transport import (
    anthropic_messages_completion_fallback,
    extract_anthropic_text,
    extract_openai_chat_text,
    extract_openai_responses_text,
    extract_text_from_litellm_response,
    litellm_completion,
    openai_chat_completion_fallback,
    openai_responses_completion_fallback,
)

logger = logging.getLogger("architec.backend_llm")

# Backward-compatible aliases for existing tests/callers.
_resolve_temperature = resolve_temperature
_prefers_openai_chat = prefers_openai_chat
_prefers_openai_responses = prefers_openai_responses
_prefers_anthropic_messages = prefers_anthropic_messages
_apply_model_map = apply_model_map
_normalize_model_name = normalize_model_name
_extract_text_from_litellm_response = extract_text_from_litellm_response
_extract_openai_chat_text = extract_openai_chat_text
_extract_openai_responses_text = extract_openai_responses_text
_extract_anthropic_text = extract_anthropic_text
_openai_chat_completion_fallback = openai_chat_completion_fallback
_openai_responses_completion_fallback = openai_responses_completion_fallback
_anthropic_messages_completion_fallback = anthropic_messages_completion_fallback
_build_result = build_result
_build_gateway_proxy_provider = build_gateway_proxy_provider
_build_messages_for_candidate = build_messages_for_candidate
_provider_attempt_chain = provider_attempt_chain
_legacy_failover_policy = legacy_failover_policy
_extract_http_status_code = extract_http_status_code
_is_retryable_exception = is_retryable_exception
_retry_timeout_schedule = retry_timeout_schedule
_retry_backoff_sleep = retry_backoff_sleep
async def _complete_openai_chat(
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
        call=lambda timeout_try: _openai_chat_completion_fallback(
            provider=provider_cfg,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout_try,
            temperature=temperature,
        ),
    )


async def _complete_openai_responses(
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
        call=lambda timeout_try: _openai_responses_completion_fallback(
            provider=provider_cfg,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout_try,
            temperature=temperature,
        ),
    )


async def _complete_anthropic_messages(
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
        call=lambda timeout_try: _anthropic_messages_completion_fallback(
            provider=provider_cfg,
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            timeout=timeout_try,
            temperature=temperature,
        ),
    )


async def _complete_litellm(
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

def _resolve_runtime_context(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
) -> tuple[str, list[ArchitectLLMCandidate], str, dict[str, str], FailoverPolicy]:
    return resolve_runtime_context_strict(
        project_root,
        task=task,
        tier=tier,
        architect_cfg_loader=load_architect_backend_llm_config,
        resolve_candidates=resolve_architect_candidates,
        backend_cfg_loader=load_backend_llm_config,
        model_chooser=choose_model,
    )


async def acomplete_text(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float = 20.0,
    max_tokens: int = 700,
    required: bool = False,
) -> dict[str, Any] | None:
    effective_tier, candidates, common_system_prompt, task_prompt_prefixes, policy = (
        _resolve_runtime_context(project_root, task=task, tier=tier)
    )
    if not candidates:
        if required:
            raise BackendLLMUnavailableError(
                "backend llm config missing under "
                f"{resolve_architect_llm_config_file(project_root)} "
                "and legacy llm-proxy/.llmgateway.yaml"
            )
        return None

    messages = build_messages_for_candidate(
        common_system_prompt=common_system_prompt,
        task_prompt_prefixes=task_prompt_prefixes,
        task=task,
        prompt=prompt,
    )
    result, last_error = await run_candidate_chain(
        candidates=candidates,
        project_root=str(project_root),
        task=task,
        messages=messages,
        effective_tier=effective_tier,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        required=required,
        policy=policy,
        normalize_model_name=normalize_model_name,
        resolve_temperature=resolve_temperature,
        record_success=record_success,
        record_transport_failure=record_transport_failure,
        prefers_openai_responses=prefers_openai_responses,
        prefers_openai_chat=prefers_openai_chat,
        prefers_anthropic_messages=prefers_anthropic_messages,
        provider_attempt_chain=provider_attempt_chain,
        complete_openai_responses=_complete_openai_responses,
        complete_openai_chat=_complete_openai_chat,
        complete_anthropic_messages=_complete_anthropic_messages,
        complete_litellm=_complete_litellm,
    )
    if result is not None:
        return result

    if required:
        if last_error is not None:
            raise BackendLLMUnavailableError(
                f"backend llm candidate chain failed task={task} tier={effective_tier} "
                f"err_type={type(last_error).__name__}: {last_error!r}"
            ) from last_error
        raise BackendLLMUnavailableError(
            f"backend llm candidate chain failed task={task} tier={effective_tier}"
        )
    return None


def complete_text(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float = 20.0,
    max_tokens: int = 700,
    required: bool = False,
) -> dict[str, Any] | None:
    try:
        return asyncio.run(
            acomplete_text(
                project_root,
                task=task,
                tier=tier,
                prompt=prompt,
                timeout_sec=timeout_sec,
                max_tokens=max_tokens,
                required=required,
            )
        )
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                acomplete_text(
                    project_root,
                    task=task,
                    tier=tier,
                    prompt=prompt,
                    timeout_sec=timeout_sec,
                    max_tokens=max_tokens,
                    required=required,
                )
            )
        finally:
            loop.close()


def complete_json(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float = 20.0,
    max_tokens: int = 700,
    required: bool = True,
) -> dict[str, Any] | None:
    provider_hint, candidate_count, policy = resolve_provider_hint_context(
        resolve_runtime_context_fn=_resolve_runtime_context,
        normalize_model_name_fn=normalize_model_name,
        project_root=str(project_root),
        task=task,
        tier=tier,
        legacy_failover_policy_fn=legacy_failover_policy,
    )

    cached = load_cached_result(
        project_root,
        task=task,
        tier=tier,
        prompt=prompt,
        provider_hint=provider_hint,
    )
    if isinstance(cached, dict) and cached:
        return cached

    last_parse_error: BackendLLMResponseError | None = None
    for _ in range(candidate_count):
        raw = complete_text(
            project_root,
            task=task,
            tier=tier,
            prompt=prompt,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
            required=required,
        )
        attempt = process_json_attempt(
            raw=raw,
            task=task,
            tier=tier,
            required=required,
            policy=policy,
            record_parse_failure_fn=record_parse_failure,
            logger=logger,
        )
        if attempt.get("kind") == "success":
            obj = attempt.get("payload", {})
            save_cached_result(
                project_root,
                task=task,
                tier=tier,
                prompt=prompt,
                provider_hint=provider_hint,
                value=obj,
            )
            return obj
        if attempt.get("kind") == "stop_none":
            return None
        err = attempt.get("error")
        if isinstance(err, BackendLLMResponseError):
            last_parse_error = err

    if required and last_parse_error is not None:
        raise last_parse_error
    return None


__all__ = ["ArchitectLLMCandidate", "BackendLLMConfig", "BackendLLMError", "BackendLLMResponseError", "BackendLLMUnavailableError", "FailoverPolicy", "acomplete_text", "complete_json", "complete_text"]
