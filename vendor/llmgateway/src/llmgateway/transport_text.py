from __future__ import annotations


def _extract_text_parts(content: object) -> list[str]:
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
        text = item.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
    return parts


def extract_openai_chat_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
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
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        parts.extend(_extract_text_parts(content))
    return "\n".join(parts)


def extract_anthropic_text(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    preferred: list[str] = []
    fallback: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if not isinstance(text, str) or not text:
            continue
        if str(item.get("type", "") or "").strip().lower() == "text":
            preferred.append(text)
        else:
            fallback.append(text)
    parts = preferred or fallback
    return "\n".join(parts)


def extract_text_from_litellm_response(response: object) -> str:
    if response is None:
        return ""
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return ""

    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, dict):
        message = first.get("message")
    if message is None:
        return ""

    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, str):
        return content

    parts = _extract_text_parts(content)
    return "\n".join(parts)


__all__ = [
    "extract_anthropic_text",
    "extract_openai_chat_text",
    "extract_openai_responses_text",
    "extract_text_from_litellm_response",
]
