from __future__ import annotations

from typing import Any, Callable

from .backend_llm_errors import BackendLLMResponseError, BackendLLMUnavailableError
from .backend_llm_parse import parse_json_object


def _build_success_payload(raw: dict[str, Any]) -> dict[str, Any]:
    obj = parse_json_object(str(raw.get("text", "") or ""))
    if obj is None:
        return {}
    obj["_llm_model"] = raw.get("model", "")
    obj["_llm_model_requested"] = raw.get("requested_model", "")
    obj["_llm_tier"] = raw.get("tier", "")
    obj["_llm_provider"] = raw.get("provider", "")
    obj["_llm_provider_route"] = raw.get("provider_route", "")
    return obj


def _handle_non_json_payload(
    *,
    raw: dict[str, Any],
    task: str,
    effective_tier: str,
    required: bool,
    policy: Any,
    record_parse_failure_fn: Callable[..., None],
    logger: Any,
) -> dict[str, Any]:
    provider_key = str(raw.get("provider_key", "") or "")
    if provider_key:
        record_parse_failure_fn(provider_key, policy=policy)
    if not required:
        return {"kind": "stop_none"}
    model = str(raw.get("model", "") or "")
    provider = str(raw.get("provider", "") or "")
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
    obj = _build_success_payload(raw)
    if obj:
        return {"kind": "success", "payload": obj}
    return _handle_non_json_payload(
        raw=raw,
        task=task,
        effective_tier=effective_tier,
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
    legacy_failover_policy_fn: Callable[[], Any],
) -> tuple[str, int, Any]:
    provider_hint = ""
    candidate_count = 1
    policy = legacy_failover_policy_fn()
    try:
        effective_tier, candidates, _, _, policy = resolve_runtime_context_fn(
            project_root,
            task=task,
            tier=tier,
        )
        candidate_count = max(1, len(candidates))
        if candidates:
            first = candidates[0]
            normalized = normalize_model_name_fn(first.provider, first.requested_model)
            provider_hint = (
                f"{first.provider_name}:{first.provider.get('api_style', '')}:"
                f"{normalized}:{effective_tier}"
            )
    except Exception:
        provider_hint = ""
    return provider_hint, candidate_count, policy
