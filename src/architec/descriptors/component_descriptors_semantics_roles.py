from __future__ import annotations

from pathlib import Path
from typing import Any


_ROLE_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("interface_adapter", ("gateway", "http", "api", "server", "transport", "mcp")),
    ("orchestration", ("ops", "workflow", "orchestr", "lifecycle")),
    ("state_storage", ("store", "memory", "cache", "repo", "storage", "db")),
    ("routing_navigation", ("nav", "route", "router", "routing")),
)


def _role_text(component: str, files: list[str]) -> str:
    return " ".join([component, *files]).lower()


def _matches_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def infer_layer_role(component: str, files: list[str]) -> str:
    text = _role_text(component, files)
    if component.endswith(":tests") or "/tests/" in text:
        return "tests"
    for role, markers in _ROLE_MARKERS:
        if _matches_marker(text, markers):
            return role
    return "application_domain"


def _summary_clause(prefix: str, value: str) -> str:
    return f"{prefix}{value}." if value else ""


def _hotspot_text(hotspots: list[dict[str, Any]]) -> str:
    return ", ".join(
        Path(str(item.get("path", "") or "")).name
        for item in hotspots[:2]
        if isinstance(item, dict) and str(item.get("path", "") or "")
    )


def _neighbor_text(neighbors: list[dict[str, Any]]) -> str:
    return ", ".join(
        str(item.get("target_component", "") or "")
        for item in neighbors[:3]
        if isinstance(item, dict) and str(item.get("target_component", "") or "")
    )


def build_responsibility_summary(
    *,
    component: str,
    files: list[str],
    symbols: list[str],
    neighbors: list[dict[str, Any]],
    layer_role: str,
    hotspots: list[dict[str, Any]],
) -> str:
    role = layer_role.replace("_", " ").strip() or "application domain"
    article = "an" if role[:1].lower() in {"a", "e", "i", "o", "u"} else "a"
    symbol_text = ", ".join(symbols[:3]) if symbols else "no clear dominant public surface"
    hotspot_text = _hotspot_text(hotspots)
    neighbor_text = _neighbor_text(neighbors)
    clauses = [
        f"{component} is {article} {role} component spanning {len(files)} files.",
        f"Primary surfaces: {symbol_text}.",
    ]
    extra = [
        _summary_clause("Current pressure points: ", hotspot_text),
        _summary_clause("Primary adjacent components: ", neighbor_text),
    ]
    return " ".join([part for part in [*clauses, *extra] if part]).strip()
