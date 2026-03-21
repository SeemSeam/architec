from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]{1,}")
_GENERIC_DESCRIPTOR_TOKENS = {
    "component",
    "module",
    "service",
    "system",
    "core",
    "common",
    "utils",
    "helper",
    "manager",
    "file",
    "files",
    "layer",
}


def _descriptor_texts(descriptor: dict[str, Any]) -> list[str]:
    texts: list[str] = [
        str(descriptor.get("component", "") or ""),
        str(descriptor.get("layer_role", "") or ""),
        str(descriptor.get("responsibility_summary", "") or ""),
    ]
    texts.extend(str(item or "") for item in descriptor.get("primary_symbols", [])[:8])
    texts.extend(str(item or "") for item in descriptor.get("files", [])[:8])
    return texts


def _normalized_descriptor_tokens(text: str) -> list[str]:
    raw = str(text or "").lower().replace("/", " ").replace("-", " ").replace(".", " ").replace(":", " ")
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(raw)]


def descriptor_terms(descriptor: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for text in _descriptor_texts(descriptor):
        for token in _normalized_descriptor_tokens(text):
            if len(token) < 4 or token in _GENERIC_DESCRIPTOR_TOKENS or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens[:24]


def descriptor_confidence(descriptor: dict[str, Any]) -> float:
    file_count = int(descriptor.get("file_count", 0) or 0)
    symbol_count = len(descriptor.get("primary_symbols", []))
    hotspot_count = len(descriptor.get("top_hotspots", []))
    neighbor_count = len(descriptor.get("dependency_neighbors", []))
    score = 0.35
    if file_count >= 1:
        score += 0.15
    if file_count >= 3:
        score += 0.1
    if symbol_count >= 2:
        score += 0.15
    if hotspot_count > 0:
        score += 0.1
    if neighbor_count > 0:
        score += 0.05
    return round(min(0.95, score), 2)


def descriptor_search_text(descriptor: dict[str, Any]) -> str:
    parts: list[str] = _descriptor_texts(descriptor)[:3]
    for field in ("primary_symbols", "descriptor_terms", "test_anchors"):
        values = descriptor.get(field, [])
        if not isinstance(values, list):
            continue
        for item in values:
            parts.append(str(item or ""))
    parts.extend(_dependency_neighbor_parts(descriptor.get("dependency_neighbors", [])))
    return "\n".join(part for part in parts if part)


def _dependency_neighbor_parts(neighbors: object) -> list[str]:
    if not isinstance(neighbors, list):
        return []
    parts: list[str] = []
    for neighbor in neighbors:
        if not isinstance(neighbor, dict):
            continue
        parts.append(str(neighbor.get("target_component", "") or ""))
        paths = neighbor.get("target_paths", [])
        if not isinstance(paths, list):
            continue
        for path in paths:
            parts.append(str(path or ""))
    return parts
