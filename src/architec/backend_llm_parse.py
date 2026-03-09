from __future__ import annotations

import ast
import json
import re
from typing import Any


def _strip_markdown_code_fence(payload: str) -> str:
    text = str(payload or "").strip()
    if text.startswith("```"):
        idx = text.find("\n")
        if idx >= 0:
            text = text[idx + 1 :]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _slice_first_json_object(text: str) -> str:
    payload = str(text or "").strip()
    if not payload or payload.startswith("{"):
        return payload
    start = payload.find("{")
    end = payload.rfind("}")
    if start >= 0 and end > start:
        return payload[start : end + 1].strip()
    return payload


def _markdown_fenced_blocks(text: str) -> list[str]:
    pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    out: list[str] = []
    for m in pattern.finditer(str(text or "")):
        block = str(m.group(1) or "").strip()
        if block:
            out.append(block)
    return out


def _balanced_object_slices(text: str, *, limit: int = 10) -> list[str]:
    payload = str(text or "")
    out: list[str] = []
    start = -1
    depth = 0
    in_string = False
    escaped = False
    for idx, ch in enumerate(payload):
        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
            continue
        if ch == "}":
            if depth <= 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = payload[start : idx + 1].strip()
                if candidate:
                    out.append(candidate)
                    if len(out) >= max(1, int(limit)):
                        break
    return out


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", str(text or ""))


def _normalize_text(text: str) -> str:
    return (
        str(text or "")
        .replace("\ufeff", "")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .strip()
    )


def _parse_dict_candidate(payload: str) -> dict[str, Any] | None:
    raw = _normalize_text(payload)
    if not raw:
        return None

    for candidate in (raw, _remove_trailing_commas(raw)):
        try:
            obj = json.loads(candidate)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            return obj

    for candidate in (raw, _remove_trailing_commas(raw)):
        try:
            obj = ast.literal_eval(candidate)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            return obj
    return None


def parse_json_object(text: str) -> dict[str, Any] | None:
    raw = str(text or "")
    stripped = _strip_markdown_code_fence(raw)
    primary = _slice_first_json_object(stripped)

    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        item = str(candidate or "").strip()
        if not item or item in seen:
            return
        seen.add(item)
        candidates.append(item)

    add(primary)
    for block in _markdown_fenced_blocks(raw):
        add(block)
    for block in _balanced_object_slices(raw):
        add(block)

    for candidate in candidates:
        obj = _parse_dict_candidate(candidate)
        if isinstance(obj, dict):
            return obj
    return None
