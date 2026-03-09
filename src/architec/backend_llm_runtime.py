from __future__ import annotations

from pathlib import Path
from typing import Any

from .backend_llm_architect_config import (
    ArchitectLLMCandidate,
    load_architect_backend_llm_config,
    resolve_architect_candidates,
)
from .backend_llm_config import BackendLLMConfig, build_messages, choose_model
from .backend_llm_failover import FailoverPolicy, ordered_candidates


def build_result(
    *,
    text: str,
    model: str,
    requested_model: str,
    tier: str,
    provider: str,
) -> dict[str, Any]:
    return {
        "ok": True,
        "text": str(text or ""),
        "model": model,
        "requested_model": requested_model,
        "tier": tier,
        "provider": provider,
    }


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
    headers = {"x-llmproxy-cwd": str(Path(project_root).resolve())}
    provider_type = "openai" if api_style.startswith("openai") else "anthropic"
    return {
        "provider_type": provider_type,
        "api_style": api_style,
        "base_url": base_url,
        "api_key": "",
        "headers": headers,
        "model_map": {},
    }


def build_messages_for_candidate(
    *,
    common_system_prompt: str,
    task_prompt_prefixes: dict[str, str],
    task: str,
    prompt: str,
) -> list[dict[str, str]]:
    shim = BackendLLMConfig(
        provider_name="architect",
        provider={},
        strong_model="",
        small_model="",
        task_models={},
        common_system_prompt=common_system_prompt,
        task_prompt_prefixes=task_prompt_prefixes,
    )
    return build_messages(shim, task=task, prompt=prompt)


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
    attempts: list[tuple[str, dict[str, Any]]] = []
    if gateway_provider is not None:
        attempts.append(("gateway", gateway_provider))
        if gateway_fallback_to_direct:
            attempts.append(("direct", provider))
        return attempts
    attempts.append(("direct", provider))
    return attempts


def legacy_failover_policy() -> FailoverPolicy:
    return FailoverPolicy(
        transport_failures_before_switch=2,
        parse_failures_before_switch=1,
        cooldown_sec=180.0,
    )


def resolve_runtime_context(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    load_backend_llm_config_fn,
) -> tuple[str, list[ArchitectLLMCandidate], str, dict[str, str], FailoverPolicy]:
    architect_cfg = load_architect_backend_llm_config(project_root)
    if architect_cfg is not None:
        effective_tier, candidates = resolve_architect_candidates(
            architect_cfg,
            task=task,
            tier=tier,
        )
        if candidates:
            return (
                effective_tier,
                ordered_candidates(candidates, policy=architect_cfg.failover_policy),
                architect_cfg.common_system_prompt,
                architect_cfg.task_prompt_prefixes,
                architect_cfg.failover_policy,
            )

    cfg = load_backend_llm_config_fn(project_root)
    if cfg is None:
        return tier, [], "", {}, legacy_failover_policy()

    requested_model = choose_model(cfg, task=task, tier=tier)
    candidate = ArchitectLLMCandidate(
        key=f"legacy:{cfg.provider_name}:{tier}",
        provider_name=cfg.provider_name,
        provider=cfg.provider,
        requested_model=requested_model,
        gateway_base_url=cfg.gateway_base_url,
        gateway_proxy_enabled=cfg.gateway_proxy_enabled,
        gateway_fallback_to_direct=cfg.gateway_fallback_to_direct,
    )
    return (
        tier,
        ordered_candidates([candidate], policy=legacy_failover_policy()),
        cfg.common_system_prompt,
        cfg.task_prompt_prefixes,
        legacy_failover_policy(),
    )
