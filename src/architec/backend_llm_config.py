from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class BackendLLMConfig:
    provider_name: str
    provider: dict[str, Any]
    strong_model: str
    small_model: str
    task_models: dict[str, str]
    common_system_prompt: str
    task_prompt_prefixes: dict[str, str]
    gateway_base_url: str = ""
    gateway_proxy_enabled: bool = False
    gateway_fallback_to_direct: bool = True


_MODEL_QUALITY_SUFFIX_RE = re.compile(
    r"^(?P<base>.+?)(?:\s+|\s*[\(\[]\s*)(?P<tier>high|medium|low)\s*[\)\]]?$",
    re.IGNORECASE,
)


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
    result: dict[str, str] = {}
    for key, value in raw.items():
        k = str(key).strip()
        v = str(value).strip()
        if k and v:
            result[k] = v
    return result


def _resolve_backend_provider(
    *,
    backend: dict[str, Any],
    cfg: dict[str, Any],
    providers: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    provider_name = str(backend.get("provider", "") or cfg.get("active_provider", "")).strip()
    provider = providers.get(provider_name, {}) if provider_name else {}
    if not isinstance(provider, dict):
        provider = {}
    return provider_name, provider


def _resolve_gateway_base_url(cfg: dict[str, Any]) -> str:
    server = cfg.get("server", {}) if isinstance(cfg.get("server"), dict) else {}
    host = str(server.get("host", "") or "").strip()
    port = server.get("port")
    if not host:
        return ""
    try:
        port_num = int(port)
    except Exception:
        return ""
    if port_num <= 0:
        return ""
    if host.startswith("http://") or host.startswith("https://"):
        return f"{host.rstrip('/')}:{port_num}"
    return f"http://{host}:{port_num}"


def load_backend_llm_config(project_root: str | Path) -> BackendLLMConfig | None:
    root = Path(project_root).resolve()
    cfg_path = root / "llm-proxy" / ".llmgateway.yaml"
    if not cfg_path.exists():
        return None

    cfg = _load_yaml(cfg_path)
    if not cfg:
        return None

    backend = cfg.get("backend_llm", {}) if isinstance(cfg.get("backend_llm"), dict) else {}
    providers = cfg.get("providers", {}) if isinstance(cfg.get("providers"), dict) else {}

    provider_name, provider = _resolve_backend_provider(
        backend=backend,
        cfg=cfg,
        providers=providers,
    )
    task_models = _string_map(backend.get("task_models", {}))
    task_prefixes = _string_map(backend.get("task_prompt_prefixes", {}))
    gateway_base_url = _resolve_gateway_base_url(cfg)

    return BackendLLMConfig(
        provider_name=provider_name,
        provider=provider,
        strong_model=str(backend.get("strong_model", "") or backend.get("model", "")).strip(),
        small_model=str(backend.get("small_model", "") or backend.get("model", "")).strip(),
        task_models=task_models,
        common_system_prompt=str(backend.get("common_system_prompt", "") or "").strip(),
        task_prompt_prefixes=task_prefixes,
        gateway_base_url=gateway_base_url,
        gateway_proxy_enabled=bool(backend.get("proxy_via_gateway", False)),
        gateway_fallback_to_direct=bool(
            backend.get("gateway_fallback_to_direct", True)
        ),
    )


def resolve_temperature(model: str, default: float = 0.0) -> float:
    name = str(model or "").strip().lower()
    if name.startswith("gpt-5"):
        return 1.0
    return float(default)


def prefers_openai_chat(provider: dict[str, Any]) -> bool:
    api_style = str(provider.get("api_style", "") or "").strip().lower()
    provider_type = str(provider.get("provider_type", "") or "").strip().lower()
    if api_style:
        return api_style == "openai_chat"
    return provider_type == "openai"


def prefers_openai_responses(provider: dict[str, Any]) -> bool:
    api_style = str(provider.get("api_style", "") or "").strip().lower()
    return api_style == "openai_responses"


def prefers_anthropic_messages(provider: dict[str, Any]) -> bool:
    api_style = str(provider.get("api_style", "") or "").strip().lower()
    provider_type = str(provider.get("provider_type", "") or "").strip().lower()
    if api_style:
        return api_style == "anthropic"
    return api_style == "anthropic" or provider_type in {"anthropic", "glm"}


def _lookup_case_insensitive_string(mapping: dict[str, Any], key: str) -> str | None:
    lowered = key.lower()
    for src, dst in mapping.items():
        if not isinstance(src, str) or src.strip().lower() != lowered:
            continue
        if not isinstance(dst, str):
            continue
        value = dst.strip()
        if value:
            return value
    return None


def apply_model_map(provider: dict[str, Any], model: str) -> str:
    raw_map = provider.get("model_map", {}) if isinstance(provider, dict) else {}
    if not isinstance(raw_map, dict) or not raw_map:
        return model

    source = str(model or "").strip()
    if not source:
        return source

    direct = raw_map.get(source)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    return _lookup_case_insensitive_string(raw_map, source) or source


def normalize_model_name(provider: dict[str, Any], model: str) -> str:
    text = " ".join(str(model or "").split()).strip()
    if not text:
        return ""

    text = apply_model_map(provider, text)
    if prefers_openai_chat(provider) or prefers_openai_responses(provider):
        match = _MODEL_QUALITY_SUFFIX_RE.match(text)
        if match:
            # OpenAI-chat endpoints generally reject whitespace quality suffixes
            # (for example "gpt-5.3-codex high"), so keep base model id.
            text = match.group("base").strip()
    return text


def choose_model(cfg: BackendLLMConfig, *, task: str, tier: str) -> str:
    task_model = str(cfg.task_models.get(task, "") or "").strip()
    if task_model:
        return task_model
    if tier == "small" and cfg.small_model:
        return cfg.small_model
    return cfg.strong_model or cfg.small_model


def build_messages(cfg: BackendLLMConfig, task: str, prompt: str) -> list[dict[str, str]]:
    content = str(prompt or "").strip()
    prefix = str(cfg.task_prompt_prefixes.get(task, "") or "").strip()
    if prefix:
        content = f"{prefix}\n\n{content}" if content else prefix

    messages: list[dict[str, str]] = []
    system = str(cfg.common_system_prompt or "").strip()
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})
    return messages
