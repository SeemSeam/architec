from __future__ import annotations

import json


def try_parse_json(text: str) -> tuple[dict | list | None, str | None]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc}"


__all__ = ["try_parse_json"]
