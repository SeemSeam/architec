from __future__ import annotations

from typing import Any


def base_hotspot_entry(item: dict[str, Any]) -> dict[str, Any] | None:
    path = str(item.get("path", "") or "").strip()
    if not path:
        return None
    samples = item.get("samples", [])
    top_metrics = item.get("top_metrics")
    return {
        "path": path,
        "component": "",
        "critical": int(item.get("critical", 0) or 0),
        "warning": int(item.get("warning", 0) or 0),
        "hotspot_score": float(item.get("score", 0.0) or 0.0),
        "component_score": None,
        "priority": "",
        "samples": samples if isinstance(samples, list) else [],
        "top_metrics": dict(top_metrics) if isinstance(top_metrics, dict) else {},
    }


def slot_defaults(path: str, *, component: str = "", priority: str = "") -> dict[str, Any]:
    return {
        "path": path,
        "component": component,
        "critical": 0,
        "warning": 0,
        "hotspot_score": 0.0,
        "component_score": None,
        "priority": priority,
        "samples": [],
        "top_metrics": {},
    }


def seed_hotspots(history: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    hotspots = history.get("hotspots", []) if isinstance(history.get("hotspots"), list) else []
    for item in hotspots:
        if not isinstance(item, dict):
            continue
        entry = base_hotspot_entry(item)
        if entry is not None:
            by_path[entry["path"]] = entry
    return by_path


def _component_slots(score: dict[str, Any]) -> list[tuple[str, float, list[dict[str, Any]]]]:
    components = score.get("components", []) if isinstance(score.get("components"), list) else []
    slots: list[tuple[str, float, list[dict[str, Any]]]] = []
    for comp in components:
        if not isinstance(comp, dict):
            continue
        refs = comp.get("hotspot_refs", []) if isinstance(comp.get("hotspot_refs"), list) else []
        slots.append(
            (
                str(comp.get("component", "") or ""),
                float(comp.get("score", 100.0) or 100.0),
                refs,
            )
        )
    return slots


def _component_slot(by_path: dict[str, dict[str, Any]], *, path: str, component: str) -> dict[str, Any]:
    slot = by_path.setdefault(path, slot_defaults(path, component=component))
    slot["component"] = slot.get("component") or component
    return slot


def _apply_component_score(slot: dict[str, Any], component_score: float) -> None:
    existing = slot.get("component_score")
    slot["component_score"] = (
        min(float(existing), component_score)
        if isinstance(existing, (int, float))
        else component_score
    )


def _apply_component_counts(slot: dict[str, Any], ref: dict[str, Any]) -> None:
    slot["critical"] = max(int(slot.get("critical", 0)), int(ref.get("critical", 0) or 0))
    slot["warning"] = max(int(slot.get("warning", 0)), int(ref.get("warning", 0) or 0))
    slot["hotspot_score"] = max(
        float(slot.get("hotspot_score", 0.0)),
        float(ref.get("score", 0.0) or 0.0),
    )


def _apply_component_ref(
    by_path: dict[str, dict[str, Any]],
    *,
    component: str,
    component_score: float,
    ref: dict[str, Any],
) -> None:
    path = str(ref.get("path", "") or "").strip()
    if not path:
        return
    slot = _component_slot(by_path, path=path, component=component)
    _apply_component_score(slot, component_score)
    _apply_component_counts(slot, ref)


def apply_component_refs(by_path: dict[str, dict[str, Any]], score: dict[str, Any]) -> None:
    for component, component_score, refs in _component_slots(score):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            _apply_component_ref(
                by_path,
                component=component,
                component_score=component_score,
                ref=ref,
            )


def _batch_files(batch: dict[str, Any]) -> list[str]:
    files = batch.get("focus_files", []) if isinstance(batch.get("focus_files"), list) else []
    return [str(raw_path or "").strip() for raw_path in files]


def _apply_batch_ref(
    by_path: dict[str, dict[str, Any]],
    *,
    path: str,
    component: str,
    priority: str,
) -> None:
    if not path:
        return
    slot = by_path.setdefault(
        path,
        slot_defaults(path, component=component, priority=priority),
    )
    if priority and not slot.get("priority"):
        slot["priority"] = priority
    if component and not slot.get("component"):
        slot["component"] = component


def apply_batch_refs(by_path: dict[str, dict[str, Any]], batches: list[dict[str, Any]]) -> None:
    for batch in batches:
        if not isinstance(batch, dict):
            continue
        priority = str(batch.get("priority", "") or "")
        component = str(batch.get("component", "") or "")
        for path in _batch_files(batch):
            _apply_batch_ref(
                by_path,
                path=path,
                component=component,
                priority=priority,
            )
