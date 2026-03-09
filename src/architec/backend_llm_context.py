from __future__ import annotations

from pathlib import Path

from .backend_llm_architect_config import (
    ArchitectLLMCandidate,
    load_architect_backend_llm_config,
    resolve_architect_candidates,
)
from .backend_llm_config import choose_model, load_backend_llm_config
from .backend_llm_errors import BackendLLMUnavailableError
from .backend_llm_failover import FailoverPolicy, ordered_candidates
from .backend_llm_runtime import legacy_failover_policy
from .resource_paths import resolve_architect_llm_config_file


def resolve_runtime_context_strict(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    architect_cfg_loader=load_architect_backend_llm_config,
    resolve_candidates=resolve_architect_candidates,
    backend_cfg_loader=load_backend_llm_config,
    model_chooser=choose_model,
) -> tuple[str, list[ArchitectLLMCandidate], str, dict[str, str], FailoverPolicy]:
    architect_cfg_path = resolve_architect_llm_config_file(project_root)
    architect_cfg = architect_cfg_loader(project_root)
    if architect_cfg_path.exists():
        if architect_cfg is None:
            raise BackendLLMUnavailableError(
                f"invalid architect backend llm config: {architect_cfg_path}"
            )
        effective_tier, candidates = resolve_candidates(
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
        raise BackendLLMUnavailableError(
            "no architect backend llm candidates configured "
            f"(task={task}, tier={tier}, config={architect_cfg_path})"
        )
    if architect_cfg is not None:
        effective_tier, candidates = resolve_candidates(
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
    cfg = backend_cfg_loader(project_root)
    if cfg is None:
        return tier, [], "", {}, legacy_failover_policy()
    requested_model = model_chooser(cfg, task=task, tier=tier)
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


__all__ = ["resolve_runtime_context_strict"]
