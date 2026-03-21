from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from .config import (
    LLMCandidate,
    build_messages,
    load_tiered_llm_config,
    resolve_tier_candidates,
)
from .errors import BackendLLMResponseError, BackendLLMUnavailableError
from .failover import FailoverPolicy, ordered_candidates
from .parse import parse_json_object
from architec.integration.resource_paths import resolve_architect_llm_config_file


def build_gateway_proxy_provider(
    *,
    gateway_proxy_enabled: bool,
    gateway_base_url: str,
    project_root: str | Path,
    api_style: str,
) -> dict[str, Any] | None:
    if not gateway_proxy_enabled:
        return None
    base_url = str(gateway_base_url or "").strip().rstrip("/")
    if not base_url:
        return None
    return {
        "provider_type": "",
        "api_style": api_style,
        "base_url": base_url,
        "api_key": "",
        "headers": {"x-llmproxy-cwd": str(Path(project_root).resolve())},
        "model_map": {},
    }


def provider_attempt_chain(
    *,
    provider: dict[str, Any],
    project_root: str | Path,
    api_style: str,
    gateway_proxy_enabled: bool,
    gateway_base_url: str,
    gateway_fallback_to_direct: bool,
) -> list[tuple[str, dict[str, Any]]]:
    gateway_provider = build_gateway_proxy_provider(
        gateway_proxy_enabled=gateway_proxy_enabled,
        gateway_base_url=gateway_base_url,
        project_root=project_root,
        api_style=api_style,
    )
    if gateway_provider is None:
        return [("direct", provider)]
    attempts: list[tuple[str, dict[str, Any]]] = [("gateway", gateway_provider)]
    if gateway_fallback_to_direct:
        attempts.append(("direct", provider))
    return attempts


def default_failover_policy() -> FailoverPolicy:
    return FailoverPolicy(
        transport_failures_before_switch=2,
        parse_failures_before_switch=1,
        cooldown_sec=180.0,
    )


def resolve_runtime_context_strict(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    tiered_cfg_loader=load_tiered_llm_config,
    resolve_candidates=resolve_tier_candidates,
) -> tuple[str, list[LLMCandidate], str, dict[str, str], FailoverPolicy]:
    tiered_cfg_path = resolve_architect_llm_config_file(project_root)
    tiered_cfg = tiered_cfg_loader(project_root)
    if tiered_cfg_path.exists():
        if tiered_cfg is None:
            raise BackendLLMUnavailableError(
                f"invalid tiered llm config: {tiered_cfg_path}"
            )
        effective_tier, candidates = resolve_candidates(tiered_cfg, task=task, tier=tier)
        if candidates:
            return (
                effective_tier,
                ordered_candidates(candidates, policy=tiered_cfg.failover_policy),
                tiered_cfg.common_system_prompt,
                tiered_cfg.task_prompt_prefixes,
                tiered_cfg.failover_policy,
            )
        raise BackendLLMUnavailableError(
            "no tiered llm candidates configured "
            f"(task={task}, tier={tier}, config={tiered_cfg_path})"
        )
    if tiered_cfg is not None:
        effective_tier, candidates = resolve_candidates(tiered_cfg, task=task, tier=tier)
        if candidates:
            return (
                effective_tier,
                ordered_candidates(candidates, policy=tiered_cfg.failover_policy),
                tiered_cfg.common_system_prompt,
                tiered_cfg.task_prompt_prefixes,
                tiered_cfg.failover_policy,
            )
    return tier, [], "", {}, default_failover_policy()


def build_messages_for_candidate(
    *,
    common_system_prompt: str,
    task_prompt_prefixes: dict[str, str],
    task: str,
    prompt: str,
) -> list[dict[str, str]]:
    return build_messages(
        common_system_prompt=common_system_prompt,
        task_prompt_prefixes=task_prompt_prefixes,
        task=task,
        prompt=prompt,
    )


async def acomplete_text_impl(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float,
    max_tokens: int,
    required: bool,
    resolve_runtime_context_fn: Callable[..., Any],
    missing_config_message: str,
    build_messages_fn: Callable[..., Any],
    run_candidate_chain_fn: Callable[..., Any],
    record_success_fn: Callable[..., Any],
    record_transport_failure_fn: Callable[..., Any],
    provider_attempt_chain_fn: Callable[..., Any],
) -> dict[str, Any] | None:
    effective_tier, candidates, common_system_prompt, task_prompt_prefixes, policy = (
        resolve_runtime_context_fn(project_root, task=task, tier=tier)
    )
    if not candidates:
        if required:
            raise BackendLLMUnavailableError(missing_config_message)
        return None
    messages = build_messages_fn(
        common_system_prompt=common_system_prompt,
        task_prompt_prefixes=task_prompt_prefixes,
        task=task,
        prompt=prompt,
    )
    result, last_error = await run_candidate_chain_fn(
        candidates=candidates,
        project_root=str(project_root),
        task=task,
        messages=messages,
        effective_tier=effective_tier,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        policy=policy,
        record_success=record_success_fn,
        record_transport_failure=record_transport_failure_fn,
        provider_attempt_chain=provider_attempt_chain_fn,
    )
    if result is not None:
        return result
    if not required:
        return None
    if last_error is not None:
        raise BackendLLMUnavailableError(
            f"backend llm candidate chain failed task={task} tier={effective_tier} "
            f"err_type={type(last_error).__name__}: {last_error!r}"
        ) from last_error
    raise BackendLLMUnavailableError(
        f"backend llm candidate chain failed task={task} tier={effective_tier}"
    )


def complete_text_impl(
    *,
    acomplete_text_fn: Callable[..., Any],
    project_root: str | Path,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float,
    max_tokens: int,
    required: bool,
) -> dict[str, Any] | None:
    kwargs = {
        "task": task,
        "tier": tier,
        "prompt": prompt,
        "timeout_sec": timeout_sec,
        "max_tokens": max_tokens,
        "required": required,
    }
    try:
        return asyncio.run(acomplete_text_fn(project_root, **kwargs))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(acomplete_text_fn(project_root, **kwargs))
        finally:
            loop.close()


def process_json_attempt(
    *,
    raw: dict[str, Any] | None,
    task: str,
    tier: str,
    required: bool,
    policy: Any,
    record_parse_failure_fn: Callable[..., None],
    logger: Any,
) -> dict[str, Any]:
    if not raw or not raw.get("ok"):
        if required:
            raise BackendLLMUnavailableError(
                f"backend llm returned no valid payload for task={task} tier={tier}"
            )
        return {"kind": "stop_none"}
    effective_tier = str(raw.get("tier", "") or tier)
    obj = parse_json_object(str(raw.get("text", "") or ""))
    if obj is not None:
        obj["_llm_model"] = raw.get("model", "")
        obj["_llm_model_requested"] = raw.get("requested_model", "")
        obj["_llm_tier"] = raw.get("tier", "")
        obj["_llm_provider"] = raw.get("provider", "")
        obj["_llm_provider_route"] = raw.get("provider_route", "")
        return {"kind": "success", "payload": obj}
    provider_key = str(raw.get("provider_key", "") or "")
    if provider_key:
        record_parse_failure_fn(provider_key, policy=policy)
    if not required:
        return {"kind": "stop_none"}
    provider = str(raw.get("provider", "") or "")
    model = str(raw.get("model", "") or "")
    sample = str(raw.get("text", "") or "").strip().replace("\n", "\\n")[:320]
    logger.warning(
        "backend llm json parse failed task=%s tier=%s provider=%s model=%s sample=%r",
        task,
        effective_tier,
        provider,
        model,
        sample,
    )
    return {
        "kind": "parse_error",
        "error": BackendLLMResponseError(
            "backend llm returned non-json response "
            f"task={task} tier={effective_tier} provider={provider} model={model}"
        ),
    }


def process_json_attempt_with_logger(
    *,
    raw: dict[str, Any] | None,
    task: str,
    tier: str,
    required: bool,
    policy: FailoverPolicy,
    process_json_attempt_fn: Callable[..., Any],
    record_parse_failure_fn: Callable[..., Any],
    logger: Any,
) -> dict[str, Any]:
    return process_json_attempt_fn(
        raw=raw,
        task=task,
        tier=tier,
        required=required,
        policy=policy,
        record_parse_failure_fn=record_parse_failure_fn,
        logger=logger,
    )


def resolve_provider_hint_context(
    *,
    resolve_runtime_context_fn: Callable[..., tuple[Any, list[Any], Any, Any, Any]],
    normalize_model_name_fn: Callable[..., str],
    project_root: str,
    task: str,
    tier: str,
    default_failover_policy_fn: Callable[[], Any],
) -> tuple[str, int, Any]:
    provider_hint = ""
    candidate_count = 1
    policy = default_failover_policy_fn()
    try:
        effective_tier, candidates, _, _, policy = resolve_runtime_context_fn(
            project_root,
            task=task,
            tier=tier,
        )
        candidate_count = max(1, len(candidates))
        if candidates:
            first = candidates[0]
            provider_hint = (
                f"{first.provider_name}:{normalize_model_name_fn(first.provider, first.requested_model)}:{effective_tier}"
            )
    except Exception:
        provider_hint = ""
    return provider_hint, candidate_count, policy


def complete_json_impl(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float,
    max_tokens: int,
    required: bool,
    resolve_provider_hint_context_fn: Callable[..., Any],
    resolve_runtime_context_fn: Callable[..., Any],
    normalize_model_name_fn: Callable[..., Any],
    default_failover_policy_fn: Callable[..., Any],
    load_cached_result_fn: Callable[..., Any],
    save_cached_result_fn: Callable[..., Any],
    complete_text_fn: Callable[..., Any],
    process_json_attempt_fn: Callable[..., Any],
) -> dict[str, Any] | None:
    provider_hint, candidate_count, policy = resolve_provider_hint_context_fn(
        resolve_runtime_context_fn=resolve_runtime_context_fn,
        normalize_model_name_fn=normalize_model_name_fn,
        project_root=str(project_root),
        task=task,
        tier=tier,
        default_failover_policy_fn=default_failover_policy_fn,
    )
    cached = load_cached_result_fn(
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
        raw = complete_text_fn(
            project_root,
            task=task,
            tier=tier,
            prompt=prompt,
            timeout_sec=timeout_sec,
            max_tokens=max_tokens,
            required=required,
        )
        attempt = process_json_attempt_fn(
            raw=raw,
            task=task,
            tier=tier,
            required=required,
            policy=policy,
        )
        if attempt.get("kind") == "success":
            payload = attempt.get("payload", {})
            save_cached_result_fn(
                project_root,
                task=task,
                tier=tier,
                prompt=prompt,
                provider_hint=provider_hint,
                value=payload,
            )
            return payload
        if attempt.get("kind") == "stop_none":
            return None
        error = attempt.get("error")
        if isinstance(error, BackendLLMResponseError):
            last_parse_error = error
    if required and last_parse_error is not None:
        raise last_parse_error
    return None


__all__ = [
    "acomplete_text_impl",
    "build_gateway_proxy_provider",
    "build_messages_for_candidate",
    "complete_json_impl",
    "complete_text_impl",
    "default_failover_policy",
    "process_json_attempt",
    "process_json_attempt_with_logger",
    "provider_attempt_chain",
    "resolve_provider_hint_context",
    "resolve_runtime_context_strict",
]
