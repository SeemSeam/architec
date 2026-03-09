from __future__ import annotations
from typing import Any, Awaitable, Callable
CompletionFn = Callable[..., Awaitable[dict[str, Any] | None]]
RouteChainFn = Callable[..., list[tuple[str, dict[str, Any]]]]
ApiStyleFn = Callable[[dict[str, Any]], bool]
async def _run_chain(
    *,
    attempts: list[tuple[str, dict[str, Any]]],
    provider_name: str,
    model: str,
    requested_model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout_sec: float,
    temperature: float,
    tier: str,
    required: bool,
    completion: CompletionFn,
) -> tuple[dict[str, Any] | None, str, Exception | None]:
    route_error: Exception | None = None
    result: dict[str, Any] | None = None
    route_name = "direct"
    for route_name, route_provider in attempts:
        try:
            result = await completion(
                provider_cfg=route_provider,
                provider_name=f"{provider_name}:{route_name}",
                model=model,
                requested_model=requested_model,
                messages=messages,
                max_tokens=max_tokens,
                timeout_sec=timeout_sec,
                temperature=temperature,
                tier=tier,
                required=required,
            )
        except Exception as exc:  # noqa: BLE001
            route_error = exc
            continue
        if result is not None:
            break
    return result, route_name, route_error


async def run_provider_attempts(
    *,
    provider: dict[str, Any],
    provider_name: str,
    project_root: str,
    messages: list[dict[str, str]],
    model: str,
    requested_model: str,
    max_tokens: int,
    timeout_sec: float,
    temperature: float,
    tier: str,
    required: bool,
    prefers_openai_responses: ApiStyleFn,
    prefers_openai_chat: ApiStyleFn,
    prefers_anthropic_messages: ApiStyleFn,
    provider_attempt_chain: RouteChainFn,
    complete_openai_responses: CompletionFn,
    complete_openai_chat: CompletionFn,
    complete_anthropic_messages: CompletionFn,
    complete_litellm: CompletionFn,
    gateway_proxy_enabled: bool,
    gateway_base_url: str,
    gateway_fallback_to_direct: bool,
) -> tuple[dict[str, Any] | None, str, Exception | None]:
    api_style = "anthropic"
    completion = complete_anthropic_messages
    if prefers_openai_responses(provider):
        api_style = "openai_responses"
        completion = complete_openai_responses
    elif prefers_openai_chat(provider):
        api_style = "openai_chat"
        completion = complete_openai_chat
    elif not prefers_anthropic_messages(provider):
        api_style = ""

    if api_style:
        attempts = provider_attempt_chain(
            provider=provider,
            project_root=project_root,
            api_style=api_style,
            gateway_proxy_enabled=gateway_proxy_enabled,
            gateway_base_url=gateway_base_url,
            gateway_fallback_to_direct=gateway_fallback_to_direct,
        )
        return await _run_chain(
            attempts=attempts,
            provider_name=provider_name,
            model=model,
            requested_model=requested_model,
            messages=messages,
            max_tokens=max_tokens,
            timeout_sec=timeout_sec,
            temperature=temperature,
            tier=tier,
            required=required,
            completion=completion,
        )

    try:
        result = await complete_litellm(
            provider_cfg=provider,
            provider_name=provider_name,
            model=model,
            requested_model=requested_model,
            messages=messages,
            max_tokens=max_tokens,
            timeout_sec=timeout_sec,
            temperature=temperature,
            tier=tier,
            required=required,
        )
        return result, "direct", None
    except Exception as exc:  # noqa: BLE001
        return None, "direct", exc
