from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .backend_llm_failover import FailoverCandidate, FailoverPolicy
from .resource_paths import resolve_architect_llm_config_file


ARCHITECT_LLM_CONFIG_NAME = "architec-llm.yaml"


_ENV_REF_RE = re.compile(
    r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-?(?P<default>[^}]*))?\}$"
)


@dataclass(frozen=True)
class ArchitectLLMCandidate(FailoverCandidate):
    provider_name: str
    provider: dict[str, Any]
    requested_model: str
    gateway_base_url: str = ""
    gateway_proxy_enabled: bool = False
    gateway_fallback_to_direct: bool = True


@dataclass(frozen=True)
class ArchitectBackendLLMConfig:
    common_system_prompt: str
    task_prompt_prefixes: dict[str, str]
    task_tiers: dict[str, str]
    failover_policy: FailoverPolicy
    candidates_by_tier: dict[str, list[ArchitectLLMCandidate]]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _string_map(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        key_text = str(key or "").strip()
        value_text = str(value or "").strip()
        if key_text and value_text:
            out[key_text] = value_text
    return out


def _provider_dict(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    provider = _resolve_env_refs(dict(raw))
    headers = provider.get("headers", {})
    model_map = provider.get("model_map", {})
    provider["headers"] = dict(headers) if isinstance(headers, dict) else {}
    provider["model_map"] = dict(model_map) if isinstance(model_map, dict) else {}
    return provider


def _resolve_env_value(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    # Support explicit env prefix: "env:ARCH_LLM_KEY"
    if text.startswith("env:") and len(text) > 4:
        return str(os.environ.get(text[4:].strip(), "") or "").strip()

    # Support shell-style placeholder: "${ARCH_LLM_KEY}" or "${ARCH_LLM_KEY:-fallback}"
    match = _ENV_REF_RE.match(text)
    if not match:
        return text
    name = str(match.group("name") or "").strip()
    default = str(match.group("default") or "")
    resolved = os.environ.get(name, default)
    return str(resolved or "").strip()


def _resolve_env_refs(value: Any) -> Any:
    if isinstance(value, str):
        return _resolve_env_value(value)
    if isinstance(value, list):
        return [_resolve_env_refs(item) for item in value]
    if isinstance(value, dict):
        return {k: _resolve_env_refs(v) for k, v in value.items()}
    return value


def _parse_policy(raw: object) -> FailoverPolicy:
    cfg = raw if isinstance(raw, dict) else {}
    return FailoverPolicy(
        transport_failures_before_switch=max(
            1, int(cfg.get("transport_failures_before_switch", 2) or 2)
        ),
        parse_failures_before_switch=max(
            1, int(cfg.get("parse_failures_before_switch", 1) or 1)
        ),
        cooldown_sec=max(1.0, float(cfg.get("cooldown_sec", 180.0) or 180.0)),
    )


def load_architect_backend_llm_config(
    project_root: str | Path,
) -> ArchitectBackendLLMConfig | None:
    cfg_path = resolve_architect_llm_config_file(project_root)
    if not cfg_path.exists():
        return None
    raw = _load_yaml(cfg_path)
    if not raw:
        return None

    providers_raw = raw.get("providers", {}) if isinstance(raw.get("providers"), dict) else {}
    providers = {str(name): _provider_dict(spec) for name, spec in providers_raw.items()}
    tiers_raw = raw.get("tiers", {}) if isinstance(raw.get("tiers"), dict) else {}
    candidates_by_tier: dict[str, list[ArchitectLLMCandidate]] = {}
    for tier_name, tier_spec in tiers_raw.items():
        tier_text = str(tier_name or "").strip()
        if not tier_text or not isinstance(tier_spec, dict):
            continue
        candidate_specs = tier_spec.get("candidates", [])
        if not isinstance(candidate_specs, list):
            continue
        resolved: list[ArchitectLLMCandidate] = []
        for index, item in enumerate(candidate_specs):
            if not isinstance(item, dict):
                continue
            provider_ref = str(item.get("provider", "") or "").strip()
            requested_model = str(item.get("model", "") or "").strip()
            provider = providers.get(provider_ref, {})
            if not provider_ref or not requested_model or not provider:
                continue
            key = str(item.get("key", "") or f"{tier_text}:{provider_ref}:{index}").strip()
            resolved.append(
                ArchitectLLMCandidate(
                    key=key,
                    provider_name=provider_ref,
                    provider=dict(provider),
                    requested_model=requested_model,
                    gateway_base_url=str(item.get("gateway_base_url", "") or "").strip(),
                    gateway_proxy_enabled=bool(item.get("gateway_proxy_enabled", False)),
                    gateway_fallback_to_direct=bool(
                        item.get("gateway_fallback_to_direct", True)
                    ),
                )
            )
        if resolved:
            candidates_by_tier[tier_text] = resolved

    if not candidates_by_tier:
        return None

    tasks_raw = raw.get("tasks", {}) if isinstance(raw.get("tasks"), dict) else {}
    task_tiers: dict[str, str] = {}
    for task_name, task_spec in tasks_raw.items():
        task_text = str(task_name or "").strip()
        if not task_text or not isinstance(task_spec, dict):
            continue
        tier_value = str(task_spec.get("tier", "") or "").strip()
        if tier_value:
            task_tiers[task_text] = tier_value

    return ArchitectBackendLLMConfig(
        common_system_prompt=str(raw.get("common_system_prompt", "") or "").strip(),
        task_prompt_prefixes=_string_map(raw.get("task_prompt_prefixes", {})),
        task_tiers=task_tiers,
        failover_policy=_parse_policy(raw.get("failover")),
        candidates_by_tier=candidates_by_tier,
    )


def resolve_architect_candidates(
    cfg: ArchitectBackendLLMConfig,
    *,
    task: str,
    tier: str,
) -> tuple[str, list[ArchitectLLMCandidate]]:
    effective_tier = str(cfg.task_tiers.get(task, "") or tier).strip() or tier
    candidates = list(cfg.candidates_by_tier.get(effective_tier, ()))
    return effective_tier, candidates
