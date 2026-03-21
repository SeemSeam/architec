from __future__ import annotations

from typing import Any, Callable

from llmgateway import Gateway, ProviderSpec, RuntimeSpec, TaskRequest, TaskSpec
from llmgateway.runtime import normalize_model_request, resolve_temperature


_ARCHITEC_GATEWAY_TASK = "__architec__"
_DEFAULT_TRANSPORT_RETRIES = 5


def _provider_spec(provider: dict[str, Any]) -> ProviderSpec:
    headers = provider.get("headers", {}) if isinstance(provider.get("headers", {}), dict) else {}
    model_map = provider.get("model_map", {}) if isinstance(provider.get("model_map", {}), dict) else {}
    return ProviderSpec(
        provider_type=str(provider.get("provider_type", "") or "").strip(),
        api_style=str(provider.get("api_style", "") or "").strip(),
        base_url=str(provider.get("base_url", "") or "").strip(),
        api_key=str(provider.get("api_key", "") or "").strip(),
        headers={str(k): str(v) for k, v in headers.items()},
        model_map={str(k): str(v) for k, v in model_map.items()},
    )


def build_runtime_spec(
    *,
    provider: dict[str, Any],
    requested_model: str,
    requested_reasoning_effort: str = "",
    timeout_sec: float,
    max_concurrent: int = 1,
) -> RuntimeSpec:
    requested = str(requested_model or "").strip()
    normalized_model, reasoning_effort = normalize_model_request(provider, requested)
    resolved_reasoning_effort = str(requested_reasoning_effort or reasoning_effort or "").strip().lower()
    return RuntimeSpec(
        provider=_provider_spec(provider),
        fallback_model=requested,
        max_concurrent=max(1, int(max_concurrent)),
        retry_max=0,
        timeout=float(timeout_sec),
        transport_retries=_DEFAULT_TRANSPORT_RETRIES,
        tasks={
            _ARCHITEC_GATEWAY_TASK: TaskSpec(
                model=requested,
                temperature=resolve_temperature(normalized_model, 0.0),
                reasoning_effort=resolved_reasoning_effort,
            )
        },
    )


async def _generate_route_result(
    *,
    provider: dict[str, Any],
    requested_model: str,
    requested_reasoning_effort: str,
    messages: list[dict[str, str]],
    timeout_sec: float,
    max_tokens: int,
) -> dict[str, Any]:
    gateway = Gateway(
        build_runtime_spec(
            provider=provider,
            requested_model=requested_model,
            requested_reasoning_effort=requested_reasoning_effort,
            timeout_sec=timeout_sec,
        )
    )
    result = await gateway.service.generate(
        TaskRequest(
            task=_ARCHITEC_GATEWAY_TASK,
            messages=list(messages),
            max_tokens=int(max_tokens),
        )
    )
    return {
        "ok": True,
        "text": result.text,
        "model": result.normalized_model,
        "requested_model": result.requested_model,
        "reasoning_effort": result.reasoning_effort,
        "temperature": result.temperature,
        "max_tokens": result.max_tokens,
    }


async def run_candidate_chain_via_gateway(
    *,
    candidates: list[Any],
    project_root: str,
    task: str,
    messages: list[dict[str, str]],
    effective_tier: str,
    max_tokens: int,
    timeout_sec: float,
    policy: Any,
    record_success: Callable[..., None],
    record_transport_failure: Callable[..., None],
    provider_attempt_chain: Callable[..., list[tuple[str, dict[str, Any]]]],
) -> tuple[dict[str, Any] | None, Exception | None]:
    last_error: Exception | None = None
    for candidate in candidates:
        requested_model = str(candidate.requested_model or "").strip()
        if not requested_model:
            record_transport_failure(candidate.key, policy=policy)
            last_error = RuntimeError(
                "backend llm model resolution failed "
                f"provider={candidate.provider_name} task={task} tier={effective_tier}"
            )
            continue

        attempts = provider_attempt_chain(
            provider=candidate.provider,
            project_root=project_root,
            api_style=str(candidate.provider.get("api_style", "") or "").strip(),
            gateway_proxy_enabled=bool(candidate.gateway_proxy_enabled),
            gateway_base_url=str(candidate.gateway_base_url or ""),
            gateway_fallback_to_direct=bool(candidate.gateway_fallback_to_direct),
        )
        route_error: Exception | None = None

        for route_name, route_provider in attempts:
            try:
                payload = await _generate_route_result(
                    provider=route_provider,
                    requested_model=requested_model,
                    requested_reasoning_effort=str(candidate.requested_reasoning_effort or ""),
                    messages=messages,
                    timeout_sec=timeout_sec,
                    max_tokens=max_tokens,
                )
            except Exception as exc:  # noqa: BLE001
                route_error = exc
                continue

            payload["tier"] = effective_tier
            payload["provider"] = f"{candidate.provider_name}:{route_name}"
            payload["provider_key"] = candidate.key
            if route_name == "gateway":
                payload["provider_route"] = "gateway"
            record_success(candidate.key)
            return payload, None

        record_transport_failure(candidate.key, policy=policy)
        if route_error is not None:
            last_error = route_error
            continue
        last_error = RuntimeError(
            "backend llm candidate returned empty response "
            f"provider={candidate.provider_name} requested_model={requested_model}"
        )
    return None, last_error


__all__ = [
    "build_runtime_spec",
    "run_candidate_chain_via_gateway",
]
