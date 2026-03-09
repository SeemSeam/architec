from __future__ import annotations

import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .analysis_cache import run_cached_analysis
from .backend_llm import complete_json
from .component_descriptors import load_or_build_component_descriptors
from .component_scoring_runtime import (
    aggregate_component_stats,
    build_component_entries,
    index_findings_by_path,
    llm_payload_from_components,
    update_component_registry,
)
from .component_scoring_scope import changed_files_from_env_scope
from .contract_engine import aggregate_hotspots
from .hippo_adapter import HippoSnapshot
from .io_utils import normalize_relpath, read_json, safe_int, utc_now_iso, write_json
from .llm_guard import guard_llm_result
from .paths import REGISTRY_PATH, SCORE_REPORT_PATH
from .resource_paths import resolve_config_file
from .scoring_policy import evaluate_incremental_score, load_scoring_policy

_CHANGED_FILES_SCOPE_ENV = "ARCH_SCORE_CHANGED_FILES"


def _run_git(root: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def _parse_numstat(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in (text or "").splitlines():
        parts = raw.split("\t")
        if len(parts) < 3:
            continue
        added = safe_int(parts[0], 0)
        deleted = safe_int(parts[1], 0)
        path = normalize_relpath(parts[2])
        if " => " in path:
            # rename format can include "a/{x => y}.py"; keep the right side simplified.
            path = normalize_relpath(path.split(" => ")[-1].replace("}", "").replace("{", ""))
        out.append({"path": path, "added": added, "deleted": deleted})
    return out


def _changed_files_from_env_scope() -> list[dict[str, Any]]:
    raw = str(os.environ.get(_CHANGED_FILES_SCOPE_ENV, "") or "").strip()
    if not raw:
        return []
    return changed_files_from_env_scope(raw, normalize_path=normalize_relpath)


def _changed_files(root: Path, base: str | None, head: str | None) -> list[dict[str, Any]]:
    scoped = _changed_files_from_env_scope()
    if scoped:
        return scoped

    if base and head:
        text = _run_git(root, ["diff", "--numstat", f"{base}...{head}"])
        rows = _parse_numstat(text)
        if rows:
            return rows

    # Default: uncommitted changes against HEAD.
    rows = _parse_numstat(_run_git(root, ["diff", "--numstat", "HEAD"]))
    if rows:
        return rows

    # Fallback from status when numstat is empty.
    status = _run_git(root, ["status", "--porcelain"])
    fallback: list[dict[str, Any]] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = normalize_relpath(line[3:])
        fallback.append({"path": path, "added": 0, "deleted": 0})
    return fallback


def _llm_scoring_enhancement(
    project_root: Path,
    components: list[dict[str, Any]],
) -> dict[str, Any] | None:
    payload = {
        "components": [
            {
                "component": c.get("component", ""),
                "score": c.get("score", 0),
                "grade": c.get("grade", ""),
                "recommendation": c.get("recommendation", ""),
                "critical": c.get("findings", {}).get("critical", 0),
                "warning": c.get("findings", {}).get("warning", 0),
                "churn_total": c.get("churn", {}).get("total", 0),
            }
            for c in components[:10]
        ]
    }
    prompt = (
        "You are an architecture quality reviewer. "
        "Given component scores, provide concise triage plan.\n"
        "Macro-first policy:\n"
        "- Prioritize system-level blockers (boundary/coupling/ownership/core complexity).\n"
        "- Do not over-prioritize style-only or low-impact local issues.\n"
        "- Focus on top 1-3 components with highest structural leverage.\n"
        "Output strict JSON only with schema:\n"
        "{\n"
        '  "triage":[{"component":"string","priority":"high|medium|low","reason":"string"}],\n'
        '  "release_gate":"string",\n'
        '  "notes":["string"]\n'
        "}\n\n"
        f"Input:\n{payload}"
    )
    return complete_json(
        project_root,
        task="architect_component_scoring",
        tier="small",
        prompt=prompt,
        timeout_sec=20.0,
        max_tokens=500,
    )


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
