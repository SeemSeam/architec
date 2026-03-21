from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from ..analysis.analysis_cache import run_cached_analysis
from ..descriptors.public import load_or_build_component_descriptors
from .component_scoring_runtime import (
    aggregate_component_stats,
    build_component_entries,
    index_findings_by_path,
    llm_payload_from_components,
    update_component_registry,
)
from .component_scoring_git import changed_files
from .component_scoring_git import changed_files_from_env as changed_files_from_env_scope
from .component_scoring_llm import llm_scoring_enhancement
from .contract_engine import aggregate_hotspots
from ..integration.hippo_adapter import HippoSnapshot
from ..support.io_utils import normalize_relpath, read_json, safe_int, utc_now_iso, write_json
from ..support.llm_guard import guard_llm_result
from ..integration.paths import REGISTRY_PATH, SCORE_REPORT_PATH
from ..integration.resource_paths import resolve_config_file
from .public import evaluate_incremental_score, load_scoring_policy


def _changed_files(root: Path, base: str | None, head: str | None) -> list[dict[str, Any]]:
    return changed_files(root, base=base, head=head)


def _changed_files_from_env_scope() -> list[dict[str, Any]]:
    return changed_files_from_env_scope()


def _llm_scoring_enhancement(
    project_root: Path,
    components: list[dict[str, Any]],
) -> dict[str, Any] | None:
    return llm_scoring_enhancement(project_root, components)


def score_changed_components(
    project_root: str | Path,
    *,
    base: str | None = None,
    head: str | None = None,
    llm_enabled: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    started = time.perf_counter()
    timings: dict[str, Any] = {}

    t0 = time.perf_counter()
    snapshot = HippoSnapshot.load(root)
    descriptors = load_or_build_component_descriptors(root, snapshot=snapshot, persist=False)
    policy_cfg = load_scoring_policy(root)
    changed = _changed_files(root, base=base, head=head)
    timings["changed_files"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    findings = snapshot.first_party_findings()
    findings_by_path = index_findings_by_path(findings)
    timings["findings_index"] = round(time.perf_counter() - t0, 3)

    hotspots = {item["path"]: item for item in aggregate_hotspots(findings, top_n=200)}

    t0 = time.perf_counter()
    comp_stats = aggregate_component_stats(
        snapshot=snapshot,
        changed_rows=changed,
        findings_by_path=findings_by_path,
        hotspots_by_path=hotspots,
    )
    timings["component_aggregation"] = round(time.perf_counter() - t0, 3)

    t0 = time.perf_counter()
    components = build_component_entries(comp_stats=comp_stats, descriptors=descriptors)
    timings["component_scoring"] = round(time.perf_counter() - t0, 3)

    # Update component registry history.
    t0 = time.perf_counter()
    registry_path = root / REGISTRY_PATH
    registry = read_json(registry_path, default={})
    if not isinstance(registry, dict):
        registry = {}
    components = update_component_registry(
        registry_path=registry_path,
        components=components,
        registry=registry,
    )
    timings["registry_update"] = round(time.perf_counter() - t0, 3)

    result = {
        "generated_at": utc_now_iso(),
        "base": base or "",
        "head": head or "",
        "changed_file_total": len(changed),
        "components": components,
        "summary": {
            "block": sum(1 for c in components if c["recommendation"] == "block"),
            "needs_changes": sum(1 for c in components if c["recommendation"] == "needs_changes"),
            "approve": sum(1 for c in components if c["recommendation"] == "approve"),
        },
        "incremental_score": evaluate_incremental_score(
            components=components,
            changed_file_total=len(changed),
            policy=policy_cfg,
        ),
        "policy": {
            "score_band": "A>=85, B>=70, C>=55, D>=40, E<40",
            "gate": "block if score<40 or critical>=3 in changed component",
            "scoring_policy": str(resolve_config_file(root, "scoring-policy.json")),
        },
        "runtime": {"timings": timings},
    }
    if llm_enabled:
        llm_payload = llm_payload_from_components(components)
        t0 = time.perf_counter()
        llm_part, cache_hit = run_cached_analysis(
            root,
            namespace="architect_component_scoring",
            payload=llm_payload,
            runner=lambda: guard_llm_result(
                root,
                task="architect_component_scoring",
                runner=lambda: _llm_scoring_enhancement(root, components),
            ),
        )
        timings["llm_enhancement"] = round(time.perf_counter() - t0, 3)
        result["llm_enhancement"] = llm_part
        result["runtime"]["llm_cache_hit"] = bool(cache_hit)
    result["runtime"]["total_elapsed_sec"] = round(time.perf_counter() - started, 3)
    write_json(root / SCORE_REPORT_PATH, result)
    return result
