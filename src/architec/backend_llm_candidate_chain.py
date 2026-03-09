from __future__ import annotations

from typing import Any, Awaitable, Callable

from .backend_llm_candidate_routes import run_provider_attempts


ModelNormalizeFn = Callable[[dict[str, Any], str], str]
TemperatureFn = Callable[[str, float], float]
FailoverRecordFn = Callable[..., None]
ApiStyleFn = Callable[[dict[str, Any]], bool]
RouteChainFn = Callable[..., list[tuple[str, dict[str, Any]]]]
CompletionFn = Callable[..., Awaitable[dict[str, Any] | None]]


async def run_candidate_chain(
    *,
    candidates: list[Any],
    project_root: str,
    task: str,
    messages: list[dict[str, str]],
    effective_tier: str,
    max_tokens: int,
    timeout_sec: float,
    required: bool,
    policy: Any,
    normalize_model_name: ModelNormalizeFn,
    resolve_temperature: TemperatureFn,
    record_success: FailoverRecordFn,
    record_transport_failure: FailoverRecordFn,
    prefers_openai_responses: ApiStyleFn,
    prefers_openai_chat: ApiStyleFn,
    prefers_anthropic_messages: ApiStyleFn,
    provider_attempt_chain: RouteChainFn,
    complete_openai_responses: CompletionFn,
    complete_openai_chat: CompletionFn,
    complete_anthropic_messages: CompletionFn,
    complete_litellm: CompletionFn,
) -> tuple[dict[str, Any] | None, Exception | None]:
    last_error: Exception | None = None
    for candidate in candidates:
        provider = candidate.provider
        requested_model = candidate.requested_model
        model = normalize_model_name(provider, requested_model)
        if not model:
            record_transport_failure(candidate.key, policy=policy)
            last_error = RuntimeError(
                "backend llm model resolution failed "
                f"provider={candidate.provider_name} task={task} tier={effective_tier} "
                f"requested={requested_model!r}"
            )
            continue

        result, route_name, route_error = await run_provider_attempts(
            provider=provider,
            provider_name=candidate.provider_name,
            project_root=project_root,
            messages=messages,
            model=model,
            requested_model=requested_model,
            max_tokens=max_tokens,
            timeout_sec=timeout_sec,
            temperature=resolve_temperature(model, 0.0),
            tier=effective_tier,
            required=required,
            prefers_openai_responses=prefers_openai_responses,
            prefers_openai_chat=prefers_openai_chat,
            prefers_anthropic_messages=prefers_anthropic_messages,
            provider_attempt_chain=provider_attempt_chain,
            complete_openai_responses=complete_openai_responses,
            complete_openai_chat=complete_openai_chat,
            complete_anthropic_messages=complete_anthropic_messages,
            complete_litellm=complete_litellm,
            gateway_proxy_enabled=bool(candidate.gateway_proxy_enabled),
            gateway_base_url=str(candidate.gateway_base_url or ""),
            gateway_fallback_to_direct=bool(candidate.gateway_fallback_to_direct),
        )
        if result is not None:
            record_success(candidate.key)
            result["tier"] = effective_tier
            result["provider_key"] = candidate.key
            if route_name == "gateway":
                result["provider_route"] = "gateway"
            return result, None

        record_transport_failure(candidate.key, policy=policy)
        if route_error is not None:
            last_error = route_error
            continue
        last_error = RuntimeError(
            "backend llm candidate returned empty response "
            f"provider={candidate.provider_name} model={model} requested_model={requested_model}"
        )
    return None, last_error
