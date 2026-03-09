from __future__ import annotations

from typing import Any


def _extract_text_parts(
    content: object,
    *,
    allowed_types: set[str] | None = None,
) -> list[str]:
    if isinstance(content, str):
        return [content] if content else []
    if not isinstance(content, list):
        return []

    parts: list[str] = []
    for item in content:
        if isinstance(item, str) and item:
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        if allowed_types is not None:
            item_type = str(item.get("type", "") or "").strip().lower()
            if item_type and item_type not in allowed_types:
                continue
        text = item.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return parts


def extract_text_from_litellm_response(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        return ""
    msg = getattr(choices[0], "message", None)
    content = getattr(msg, "content", "") if msg is not None else ""
    if isinstance(content, str):
        return content
    return str(content or "")


def extract_openai_chat_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message", {})
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content", "")
    parts = _extract_text_parts(content)
    if parts:
        return "\n".join(parts)
    return str(content or "")


def extract_openai_responses_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text
    if isinstance(output_text, list):
        parts = [str(x) for x in output_text if isinstance(x, str) and x]
        if parts:
            return "\n".join(parts)

    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, str) and content:
            parts.append(content)
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, str) and block:
                parts.append(block)
                continue
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(parts)


def extract_anthropic_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    content = payload.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    # Prefer final text blocks, then fallback for compatibility.
    parts = _extract_text_parts(content, allowed_types={"text"})
    if not parts:
        parts = _extract_text_parts(content)
    return "\n".join(parts)
