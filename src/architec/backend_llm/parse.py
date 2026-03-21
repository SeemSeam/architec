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
    return [str(match.group(1) or "").strip() for match in pattern.finditer(str(text or "")) if str(match.group(1) or "").strip()]


def _scan_state(
    *,
    ch: str,
    start: int,
    depth: int,
    in_string: bool,
    escaped: bool,
    idx: int,
) -> tuple[int, int, bool, bool]:
    if in_string:
        if escaped:
            return start, depth, in_string, False
        if ch == "\\":
            return start, depth, in_string, True
        if ch == '"':
            return start, depth, False, False
        return start, depth, in_string, escaped
    if ch == '"':
        return start, depth, True, False
    if ch == "{":
        return (idx if depth == 0 else start), depth + 1, False, False
    if ch == "}":
        return start, max(0, depth - 1), False, False
    return start, depth, False, False


def _balanced_object_slices(text: str, *, limit: int = 10) -> list[str]:
    payload = str(text or "")
    out: list[str] = []
    start = -1
    depth = 0
    in_string = False
    escaped = False
    for idx, ch in enumerate(payload):
        depth_before = depth
        start, depth, in_string, escaped = _scan_state(
            ch=ch,
            start=start,
            depth=depth,
            in_string=in_string,
            escaped=escaped,
            idx=idx,
        )
        if depth_before > 0 and depth == 0 and start >= 0:
            out.append(payload[start : idx + 1].strip())
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
    for parser in (json.loads, ast.literal_eval):
        for candidate in (raw, _remove_trailing_commas(raw)):
            try:
                obj = parser(candidate)
            except Exception:
                obj = None
            if isinstance(obj, dict):
                return obj
    return None


def _candidate_payloads(raw: str) -> list[str]:
    stripped = _strip_markdown_code_fence(raw)
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        item = str(candidate or "").strip()
        if item and item not in seen:
            seen.add(item)
            candidates.append(item)

    add(_slice_first_json_object(stripped))
    for block in _markdown_fenced_blocks(raw):
        add(block)
    for block in _balanced_object_slices(raw):
        add(block)
    return candidates


def parse_json_object(text: str) -> dict[str, Any] | None:
    for candidate in _candidate_payloads(str(text or "")):
        obj = _parse_dict_candidate(candidate)
        if isinstance(obj, dict):
            return obj
    return None


__all__ = ["parse_json_object"]
