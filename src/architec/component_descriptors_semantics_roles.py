from __future__ import annotations

from pathlib import Path
from typing import Any


def infer_layer_role(component: str, files: list[str]) -> str:
    text = " ".join([component, *files]).lower()
    if component.endswith(":tests") or "/tests/" in text:
        return "tests"
    if any(marker in text for marker in ("gateway", "http", "api", "server", "transport", "mcp")):
        return "interface_adapter"
    if any(marker in text for marker in ("ops", "workflow", "orchestr", "lifecycle")):
        return "orchestration"
    if any(marker in text for marker in ("store", "memory", "cache", "repo", "storage", "db")):
        return "state_storage"
    if any(marker in text for marker in ("nav", "route", "router", "routing")):
        return "routing_navigation"
    return "application_domain"


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
    hotspot_text = ", ".join(
        Path(str(item.get("path", "") or "")).name
        for item in hotspots[:2]
        if isinstance(item, dict) and str(item.get("path", "") or "")
    )
    neighbor_text = ", ".join(
        str(item.get("target_component", "") or "")
        for item in neighbors[:3]
        if isinstance(item, dict) and str(item.get("target_component", "") or "")
    )
    clauses = [
        f"{component} is {article} {role} component spanning {len(files)} files.",
        f"Primary surfaces: {symbol_text}.",
    ]
    if hotspot_text:
        clauses.append(f"Current pressure points: {hotspot_text}.")
    if neighbor_text:
        clauses.append(f"Primary adjacent components: {neighbor_text}.")
    return " ".join(clauses).strip()
