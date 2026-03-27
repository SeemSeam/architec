from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from architec.integration.hippo_adapter import EXCLUDED_FINDING_PREFIXES, HippoSnapshot, split_symbol_ref
from architec.support.io_utils import normalize_relpath
from architec.support.path_policy import path_kind


def _is_noise_dependency_path(path: str) -> bool:
    norm = normalize_relpath(path)
    if not norm:
        return True
    return path_kind(norm) in {"test", "doc", "fixture", "generated", "excluded", "hidden", "infra"}


def _iter_component_edges(snapshot: HippoSnapshot) -> list[tuple[str, str, int]]:
    deps_fn = getattr(snapshot, "function_dependencies", None)
    deps = deps_fn() if callable(deps_fn) else {}
    edges: list[tuple[str, str, int]] = []
    for source_ref, raw_edges in deps.items():
        src_path, _ = split_symbol_ref(source_ref)
        src_component = snapshot.component_for_path(src_path)
        if not src_component:
            continue
        for edge in raw_edges:
            target_ref = str(edge.get("target", "") or "")
            weight = max(1, int(edge.get("weight", 1) or 1))
            dst_path, _ = split_symbol_ref(target_ref)
            edges.append((src_component, dst_path, weight))
    return edges


def _should_skip_component_edge(src_component: str, dst_path: str, dst_component: str) -> bool:
    if not dst_path or any(dst_path.startswith(prefix) for prefix in EXCLUDED_FINDING_PREFIXES):
        return True
    if _is_noise_dependency_path(dst_path):
        return True
    if not dst_component or dst_component == src_component:
        return True
    return dst_component.endswith(":tests") or dst_component.startswith("tmp_")


def _record_component_edge(
    *,
    src_component: str,
    dst_component: str,
    dst_path: str,
    weight: int,
    adjacency: dict[str, Counter[str]],
    path_refs: dict[tuple[str, str], Counter[str]],
) -> None:
    adjacency[src_component][dst_component] += weight
    path_refs[(src_component, dst_component)][normalize_relpath(dst_path)] += weight


def _edge_records(
    adjacency: dict[str, Counter[str]],
    path_refs: dict[tuple[str, str], Counter[str]],
    src_component: str,
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for dst_component, weight in adjacency[src_component].most_common():
        refs = path_refs.get((src_component, dst_component), Counter())
        edges.append(
            {
                "target_component": dst_component,
                "weight": int(weight),
                "target_paths": [path for path, _ in refs.most_common(6)],
            }
        )
    return edges


def build_component_graph(snapshot: HippoSnapshot) -> dict[str, list[dict[str, Any]]]:
    adjacency: dict[str, Counter[str]] = defaultdict(Counter)
    path_refs: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for src_component, dst_path, weight in _iter_component_edges(snapshot):
        dst_component = snapshot.component_for_path(dst_path)
        if _should_skip_component_edge(src_component, dst_path, dst_component):
            continue
        _record_component_edge(
            src_component=src_component,
            dst_component=dst_component,
            dst_path=dst_path,
            weight=weight,
            adjacency=adjacency,
            path_refs=path_refs,
        )

    out: dict[str, list[dict[str, Any]]] = {}
    for src_component in adjacency:
        out[src_component] = _edge_records(adjacency, path_refs, src_component)
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
