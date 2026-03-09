from __future__ import annotations

import asyncio
import threading
from typing import Any

from .backend_llm_transport_payloads import (
    build_anthropic_headers as _build_anthropic_headers,
    build_anthropic_payload as _build_anthropic_payload,
    build_openai_chat_url as _build_openai_chat_url,
    build_openai_headers as _build_openai_headers,
    build_openai_responses_payload as _build_openai_responses_payload,
    build_openai_responses_url as _build_openai_responses_url,
)
from .backend_llm_transport_text import (
    extract_anthropic_text,
    extract_openai_chat_text,
    extract_openai_responses_text,
    extract_text_from_litellm_response,
)

_SYNC_HTTP_CLIENT = None
_SYNC_HTTP_CLIENT_LOCK = threading.Lock()


def _get_sync_http_client():
    import httpx

    global _SYNC_HTTP_CLIENT
    with _SYNC_HTTP_CLIENT_LOCK:
        if _SYNC_HTTP_CLIENT is None or _SYNC_HTTP_CLIENT.is_closed:
            _SYNC_HTTP_CLIENT = httpx.Client(
                timeout=httpx.Timeout(30.0),
                http2=True,
                limits=httpx.Limits(
                    max_connections=50,
                    max_keepalive_connections=20,
                    keepalive_expiry=45.0,
                ),
            )
    return _SYNC_HTTP_CLIENT


def _sync_post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> object:
    client = _get_sync_http_client()
    resp = client.post(
        url,
        headers=headers,
        json=payload,
        timeout=float(timeout),
    )
    resp.raise_for_status()
    return resp.json()


async def _post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> object:
    return await asyncio.to_thread(
        _sync_post_json,
        url=url,
        headers=headers,
        payload=payload,
        timeout=timeout,
    )


async def openai_chat_completion_fallback(
    *,
    provider: dict[str, Any],
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: float,
    temperature: float,
) -> str:
    url = _build_openai_chat_url(provider)
    if not url:
        return ""
    headers = _build_openai_headers(provider)
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "stream": False,
    }
    data = await _post_json(
        url=url,
        headers=headers,
        payload=payload,
        timeout=timeout,
    )
    return extract_openai_chat_text(data)


async def openai_responses_completion_fallback(
    *,
    provider: dict[str, Any],
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: float,
    temperature: float,
) -> str:
    url = _build_openai_responses_url(provider)
    if not url:
        return ""
    headers = _build_openai_headers(provider)
    payload = _build_openai_responses_payload(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    data = await _post_json(
        url=url,
        headers=headers,
        payload=payload,
        timeout=timeout,
    )
    return extract_openai_responses_text(data)


async def anthropic_messages_completion_fallback(
    *,
    provider: dict[str, Any],
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: float,
    temperature: float,
) -> str:
    base_url = str(provider.get("base_url", "") or "").strip().rstrip("/")
    if not base_url:
        return ""
    url = f"{base_url}/v1/messages"
    headers = _build_anthropic_headers(provider)
    payload = _build_anthropic_payload(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    data = await _post_json(
        url=url,
        headers=headers,
        payload=payload,
        timeout=timeout,
    )
    return extract_anthropic_text(data)


async def litellm_completion(
    *,
    provider: dict[str, Any],
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout: float,
    temperature: float,
) -> str:
    import litellm

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "timeout": float(timeout),
    }
    base_url = str(provider.get("base_url", "") or "").strip()
    api_key = str(provider.get("api_key", "") or "").strip()
    headers = provider.get("headers", {}) or {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    if isinstance(headers, dict) and headers:
        kwargs["extra_headers"] = headers

    resp = await litellm.acompletion(**kwargs)
    return extract_text_from_litellm_response(resp)
