from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llmgateway.config import (
    load_user_config as load_gateway_user_config,
    runtime_spec_from_dict,
)
from llmgateway.runtime import normalize_model_request

from architec.integration.resource_paths import (
    package_config_dir,
    resolve_architect_llm_config_file,
    resolve_prompt_file,
)

from .failover import FailoverCandidate, FailoverPolicy


LLM_CONFIG_NAME = "config.default.yaml"
_ENV_REF_RE = re.compile(
    r"^\$\{(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?::-?(?P<default>[^}]*))?\}$"
)


@dataclass(frozen=True)
class LLMCandidate(FailoverCandidate):
    provider_name: str
    provider: dict[str, Any]
    requested_model: str
    requested_reasoning_effort: str = ""
    gateway_base_url: str = ""
    gateway_proxy_enabled: bool = False
    gateway_fallback_to_direct: bool = True


@dataclass(frozen=True)
class TieredLLMConfig:
    common_system_prompt: str
    task_prompt_prefixes: dict[str, str]
    task_tiers: dict[str, str]
    failover_policy: FailoverPolicy
    candidates_by_tier: dict[str, list[LLMCandidate]]


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


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _resolve_prompt_text(project_root: str | Path, value: object) -> str:
    text = str(value or "").strip()
    if not text.startswith("prompt:"):
        return text
    name = text[len("prompt:") :].strip()
    if not name:
        return ""
    path = resolve_prompt_file(project_root, name)
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _string_map(project_root: str | Path, raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        key_text = str(key or "").strip()
        value_text = _resolve_prompt_text(project_root, value)
        if key_text and value_text:
            out[key_text] = value_text
    return out


def _resolve_env_value(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("env:") and len(text) > 4:
        return str(os.environ.get(text[4:].strip(), "") or "").strip()
    match = _ENV_REF_RE.match(text)
    if match is None:
        return text
    name = str(match.group("name") or "").strip()
    default = str(match.group("default") or "")
    return str(os.environ.get(name, default) or "").strip()


def _resolve_env_refs(value: Any) -> Any:
    if isinstance(value, str):
        return _resolve_env_value(value)
    if isinstance(value, list):
        return [_resolve_env_refs(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_env_refs(item) for key, item in value.items()}
    return value


def _provider_dict(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    provider = _resolve_env_refs(dict(raw))
    headers = provider.get("headers", {})
    model_map = provider.get("model_map", {})
    provider["headers"] = dict(headers) if isinstance(headers, dict) else {}
    provider["model_map"] = dict(model_map) if isinstance(model_map, dict) else {}
    return provider


def _dict_section(raw: dict[str, Any], key: str) -> dict[str, Any]:
    section = raw.get(key, {})
    return section if isinstance(section, dict) else {}


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


def _providers_from_raw(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    providers_raw = _dict_section(raw, "providers")
    resolved = {str(name): _provider_dict(spec) for name, spec in providers_raw.items()}
    gateway_provider = _gateway_provider_dict()
    if gateway_provider:
        resolved.setdefault("llmgateway", gateway_provider)
    return resolved


def _gateway_provider_dict() -> dict[str, Any]:
    runtime = _gateway_runtime_spec()
    if runtime is None:
        return {}
    return {
        "provider_type": str(runtime.provider.provider_type or "").strip(),
        "api_style": str(runtime.provider.api_style or "").strip(),
        "base_url": str(runtime.provider.base_url or "").strip(),
        "api_key": str(runtime.provider.api_key or "").strip(),
        "headers": dict(runtime.provider.headers or {}),
        "model_map": dict(runtime.provider.model_map or {}),
    }


def _gateway_runtime_spec():
    raw = load_gateway_user_config()
    if not raw:
        return None
    try:
        return runtime_spec_from_dict(raw)
    except Exception:
        return None


def resolve_gateway_timeout_sec(requested_timeout_sec: float) -> float:
    resolved = max(1.0, float(requested_timeout_sec or 0.0))
    runtime = _gateway_runtime_spec()
    if runtime is None:
        return resolved
    try:
        gateway_timeout = float(runtime.timeout or 0.0)
    except Exception:
        return resolved
    if gateway_timeout <= 0:
        return resolved
    return max(resolved, gateway_timeout)


def _candidate_from_spec(
    *,
    tier_text: str,
    index: int,
    item: object,
    providers: dict[str, dict[str, Any]],
    default_provider_name: str,
) -> LLMCandidate | None:
    if not isinstance(item, dict):
        return None
    provider_ref = str(item.get("provider", "") or default_provider_name).strip()
    requested_model = str(item.get("model", "") or "").strip()
    requested_reasoning_effort = str(item.get("reasoning_effort", "") or "").strip().lower()
    if not requested_model:
        return None
    provider = providers.get(provider_ref, {})
    resolved_provider_name = provider_ref or default_provider_name or "llmgateway"
    key = str(item.get("key", "") or f"{tier_text}:{resolved_provider_name}:{index}").strip()
    return LLMCandidate(
        key=key,
        provider_name=resolved_provider_name,
        provider=dict(provider),
        requested_model=requested_model,
        requested_reasoning_effort=requested_reasoning_effort,
        gateway_base_url=str(item.get("gateway_base_url", "") or "").strip(),
        gateway_proxy_enabled=bool(item.get("gateway_proxy_enabled", False)),
        gateway_fallback_to_direct=bool(item.get("gateway_fallback_to_direct", True)),
    )


def _gateway_candidate_for_tier(tier_text: str) -> LLMCandidate | None:
    runtime = _gateway_runtime_spec()
    if runtime is None:
        return None
    requested_model = str(runtime.model_for_tier(tier_text) or "").strip()
    if not requested_model:
        return None
    provider = _gateway_provider_dict()
    return LLMCandidate(
        key=f"{tier_text}:llmgateway:0",
        provider_name="llmgateway",
        provider=provider,
        requested_model=requested_model,
        requested_reasoning_effort=str(runtime.reasoning_effort_for_tier(tier_text) or "").strip().lower(),
    )


def _candidates_by_tier(raw: dict[str, Any]) -> dict[str, list[LLMCandidate]]:
    providers = _providers_from_raw(raw)
    default_provider_name = "llmgateway" if "llmgateway" in providers else ""
    tiers_raw = _dict_section(raw, "tiers")
    resolved: dict[str, list[LLMCandidate]] = {}
    for tier_name, tier_spec in tiers_raw.items():
        tier_text = str(tier_name or "").strip()
        if not tier_text or not isinstance(tier_spec, dict):
            continue
        candidate_specs = tier_spec.get("candidates", [])
        if not isinstance(candidate_specs, list) and any(
            key in tier_spec for key in ("model", "reasoning_effort")
        ):
            candidate_specs = [tier_spec]
        if not isinstance(candidate_specs, list):
            continue
        candidates = [
            candidate
            for index, item in enumerate(candidate_specs)
            for candidate in [
                _candidate_from_spec(
                    tier_text=tier_text,
                    index=index,
                    item=item,
                    providers=providers,
                    default_provider_name=default_provider_name,
                )
            ]
            if candidate is not None
        ]
        if candidates:
            resolved.setdefault(tier_text, []).extend(candidates)
    if resolved:
        return resolved
    for tier_text in ("strong", "weak"):
        candidate = _gateway_candidate_for_tier(tier_text)
        if candidate is not None:
            resolved[tier_text] = [candidate]
    return resolved


def _task_tiers(raw: dict[str, Any]) -> dict[str, str]:
    tasks_raw = _dict_section(raw, "tasks")
    resolved: dict[str, str] = {}
    for task_name, task_spec in tasks_raw.items():
        task_text = str(task_name or "").strip()
        if not task_text or not isinstance(task_spec, dict):
            continue
        tier_value = str(task_spec.get("tier", "") or "").strip()
        if tier_value:
            resolved[task_text] = tier_value
    return resolved


def load_tiered_llm_config(
    project_root: str | Path,
) -> TieredLLMConfig | None:
    default_cfg_path = package_config_dir() / LLM_CONFIG_NAME
    cfg_path = resolve_architect_llm_config_file(project_root)
    default_raw = _load_yaml(default_cfg_path) if default_cfg_path.exists() else {}
    override_raw = _load_yaml(cfg_path) if cfg_path.exists() else {}
    raw = {}
    if default_raw:
        raw = _merge_dicts(raw, default_raw)
    if override_raw:
        raw = _merge_dicts(raw, override_raw)
    if not raw:
        return None
    candidates_by_tier = _candidates_by_tier(raw)
    if not candidates_by_tier:
        return None
    return TieredLLMConfig(
        common_system_prompt=_resolve_prompt_text(project_root, raw.get("common_system_prompt", "")),
        task_prompt_prefixes=_string_map(project_root, raw.get("task_prompt_prefixes", {})),
        task_tiers=_task_tiers(raw),
        failover_policy=_parse_policy(raw.get("failover")),
        candidates_by_tier=candidates_by_tier,
    )


def resolve_tier_candidates(
    cfg: TieredLLMConfig,
    *,
    task: str,
    tier: str,
) -> tuple[str, list[LLMCandidate]]:
    effective_tier = str(cfg.task_tiers.get(task, "") or tier).strip() or tier
    return effective_tier, list(cfg.candidates_by_tier.get(effective_tier, ()))


def normalize_model_name(provider: dict[str, Any], model: str) -> str:
    normalized, _reasoning_effort = normalize_model_request(dict(provider), model)
    return normalized


def build_messages(
    *,
    common_system_prompt: str,
    task_prompt_prefixes: dict[str, str],
    task: str,
    prompt: str,
) -> list[dict[str, str]]:
    content = str(prompt or "").strip()
    prefix = str(task_prompt_prefixes.get(task, "") or "").strip()
    if prefix:
        content = f"{prefix}\n\n{content}" if content else prefix
    messages: list[dict[str, str]] = []
    system = str(common_system_prompt or "").strip()
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})
    return messages


__all__ = [
    "LLM_CONFIG_NAME",
    "LLMCandidate",
    "TieredLLMConfig",
    "build_messages",
    "load_tiered_llm_config",
    "normalize_model_name",
    "resolve_gateway_timeout_sec",
    "resolve_tier_candidates",
]
