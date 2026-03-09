from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .hippo_adapter import EXCLUDED_FINDING_PREFIXES, HippoSnapshot, split_symbol_ref
from .io_utils import normalize_relpath


_NOISE_PATH_MARKERS = {
    "tests",
    "test",
    "tmp",
    "temp",
    "scratch",
    "fixtures",
    "__pycache__",
}


def _is_noise_dependency_path(path: str) -> bool:
    norm = normalize_relpath(path)
    if not norm:
        return True
    parts = [part.lower() for part in norm.split("/") if part]
    if any(part in _NOISE_PATH_MARKERS for part in parts):
        return True
    if any(part.startswith(("tmp_", "temp_", "scratch_")) for part in parts):
        return True
    filename = parts[-1] if parts else ""
    if filename.startswith(("test_", "tmp_", "temp_", "scratch_")):
        return True
    if "smoke" in filename or "fixture" in filename:
        return True
    return False


def build_component_graph(snapshot: HippoSnapshot) -> dict[str, list[dict[str, Any]]]:
    deps_fn = getattr(snapshot, "function_dependencies", None)
    deps = deps_fn() if callable(deps_fn) else {}
    adjacency: dict[str, Counter[str]] = defaultdict(Counter)
    path_refs: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for source_ref, edges in deps.items():
        src_path, _ = split_symbol_ref(source_ref)
        src_component = snapshot.component_for_path(src_path)
        if not src_component:
            continue
        for edge in edges:
            target_ref = str(edge.get("target", "") or "")
            weight = max(1, int(edge.get("weight", 1) or 1))
            dst_path, _ = split_symbol_ref(target_ref)
            if not dst_path or any(dst_path.startswith(prefix) for prefix in EXCLUDED_FINDING_PREFIXES):
                continue
            if _is_noise_dependency_path(dst_path):
                continue
            dst_component = snapshot.component_for_path(dst_path)
            if (
                not dst_component
                or dst_component == src_component
                or dst_component.endswith(":tests")
                or dst_component.startswith("tmp_")
            ):
                continue
            adjacency[src_component][dst_component] += weight
            path_refs[(src_component, dst_component)][normalize_relpath(dst_path)] += weight

    out: dict[str, list[dict[str, Any]]] = {}
    for src_component, counter in adjacency.items():
        edges: list[dict[str, Any]] = []
        for dst_component, weight in counter.most_common():
            refs = path_refs.get((src_component, dst_component), Counter())
            edges.append(
                {
                    "target_component": dst_component,
                    "weight": int(weight),
                    "target_paths": [path for path, _ in refs.most_common(6)],
                }
            )
        out[src_component] = edges
    return out


def component_neighbors(
    graph: dict[str, list[dict[str, Any]]],
    component: str,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    edges = graph.get(component, [])
    if not isinstance(edges, list):
        return []
    return [edge for edge in edges[: max(1, limit)] if isinstance(edge, dict)]
