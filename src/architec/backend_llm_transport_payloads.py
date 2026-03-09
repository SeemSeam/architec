from __future__ import annotations

from typing import Any


def build_openai_chat_url(provider: dict[str, Any]) -> str:
    base_url = str(provider.get("base_url", "") or "").strip().rstrip("/")
    if not base_url:
        return ""
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


def build_openai_responses_url(provider: dict[str, Any]) -> str:
    base_url = str(provider.get("base_url", "") or "").strip().rstrip("/")
    if not base_url:
        return ""
    if base_url.endswith("/responses"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/responses"
    return f"{base_url}/v1/responses"


def build_openai_headers(provider: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {"content-type": "application/json"}
    api_key = str(provider.get("api_key", "") or "").strip()
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"

    raw_headers = provider.get("headers", {}) or {}
    if not isinstance(raw_headers, dict):
        return headers

    for k, v in raw_headers.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        lk = k.strip().lower()
        if lk in {
            "authorization",
            "content-type",
            "anthropic-version",
            "anthropic-beta",
        }:
            continue
        headers[k] = v
    return headers


def build_openai_responses_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    instructions_parts: list[str] = []
    input_items: list[dict[str, Any]] = []
    for msg in messages:
        role = str(msg.get("role", "user") or "user").strip().lower()
        content = str(msg.get("content", "") or "")
        if role == "system":
            if content:
                instructions_parts.append(content)
            continue
        if role not in {"user", "assistant", "developer"}:
            role = "user"
        input_items.append(
            {
                "role": role,
                "content": [{"type": "input_text", "text": content}],
            }
        )

    payload: dict[str, Any] = {
        "model": model,
        "input": input_items
        or [{"role": "user", "content": [{"type": "input_text", "text": ""}]}],
        "max_output_tokens": int(max_tokens),
        "temperature": float(temperature),
    }
    instructions = "\n\n".join(x for x in instructions_parts if x.strip()).strip()
    if instructions:
        payload["instructions"] = instructions
    return payload


def build_anthropic_headers(provider: dict[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {"content-type": "application/json"}
    raw_headers = provider.get("headers", {}) or {}
    if isinstance(raw_headers, dict):
        for k, v in raw_headers.items():
            if isinstance(k, str) and isinstance(v, str) and k.strip():
                headers[k] = v

    api_key = str(provider.get("api_key", "") or "").strip()
    lowered = {k.lower() for k in headers}
    if api_key and "x-api-key" not in lowered:
        headers["x-api-key"] = api_key
    if api_key and "authorization" not in lowered:
        headers["authorization"] = f"Bearer {api_key}"
    if "anthropic-version" not in lowered:
        headers["anthropic-version"] = "2023-06-01"
    return headers


def build_anthropic_payload(
    *,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    system_parts: list[str] = []
    convo: list[dict[str, str]] = []
    for msg in messages:
        role = str(msg.get("role", "user"))
        content = str(msg.get("content", ""))
        if role == "system":
            system_parts.append(content)
            continue
        convo.append({"role": role, "content": content})
    if not convo:
        convo = [{"role": "user", "content": ""}]

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": int(max_tokens),
        "messages": convo,
        "temperature": float(temperature),
    }
    system_text = "\n".join(system_parts).strip()
    if system_text:
        payload["system"] = system_text
    return payload
