from __future__ import annotations

import re
from typing import Any


_MODEL_QUALITY_SUFFIX_RE = re.compile(
    r"^(?P<base>.+?)(?:\s+|\s*[\(\[]\s*)(?P<tier>minimal|low|medium|high)\s*[\)\]]?$",
    re.IGNORECASE,
)


def apply_model_map(provider: dict[str, Any], model: str) -> str:
    raw_map = provider.get("model_map", {})
    if not isinstance(raw_map, dict) or not raw_map:
        return model
    text = str(model or "").strip()
    if not text:
        return text
    direct = raw_map.get(text)
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    lowered = text.lower()
    for src, dst in raw_map.items():
        if isinstance(src, str) and isinstance(dst, str) and src.strip().lower() == lowered and dst.strip():
            return dst.strip()
    return text


def normalize_model_request(provider: dict[str, Any], model: str) -> tuple[str, str | None]:
    text = apply_model_map(provider, " ".join(str(model or "").split()).strip())
    if prefers_openai_chat(provider) or prefers_openai_responses(provider):
        match = _MODEL_QUALITY_SUFFIX_RE.match(text)
        if match:
            return match.group("base").strip(), match.group("tier").strip().lower()
    return text, None


def prefers_openai_responses(provider: dict[str, Any]) -> bool:
    api_style = str(provider.get("api_style", "") or "").strip().lower()
    if api_style:
        return api_style == "openai_responses"
    provider_type = str(provider.get("provider_type", "") or "").strip().lower()
    return provider_type == "glm"


def prefers_openai_chat(provider: dict[str, Any]) -> bool:
    api_style = str(provider.get("api_style", "") or "").strip().lower()
    if api_style:
        return api_style == "openai_chat"
    provider_type = str(provider.get("provider_type", "") or "").strip().lower()
    return provider_type == "openai"


def prefers_litellm(provider: dict[str, Any]) -> bool:
    api_style = str(provider.get("api_style", "") or "").strip().lower()
    if api_style:
        return api_style == "litellm"
    provider_type = str(provider.get("provider_type", "") or "").strip().lower()
    return provider_type == "litellm"


def prefers_anthropic_messages(provider: dict[str, Any], model: str) -> bool:
    api_style = str(provider.get("api_style", "") or "").strip().lower()
    if api_style:
        return api_style == "anthropic"
    provider_type = str(provider.get("provider_type", "") or "").strip().lower()
    if provider_type == "anthropic":
        return True
    return str(model or "").strip().lower().startswith("claude")


def resolve_temperature(model: str, default: float = 0.0) -> float:
    name = str(model or "").strip().lower()
    if name.startswith("gpt-5"):
        return 1.0
    return float(default)


__all__ = [
    "apply_model_map",
    "normalize_model_request",
    "prefers_anthropic_messages",
    "prefers_litellm",
    "prefers_openai_chat",
    "prefers_openai_responses",
    "resolve_temperature",
]
