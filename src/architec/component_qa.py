from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .backend_llm import complete_json
from .component_descriptors import (
    descriptor_search_text,
    load_or_build_component_descriptors,
)
from .component_graph import build_component_graph, component_neighbors
from .component_selection_policy import (
    is_infra_component,
    query_targets_infra,
    query_targets_tests,
)
from .contract_engine import aggregate_hotspots
from .hippo_adapter import HippoSnapshot
from .io_utils import normalize_relpath, utc_now_iso, write_json
from .llm_guard import guard_llm_result
from .paths import QA_REPORT_PATH


def _infer_component(snapshot: HippoSnapshot, question: str, preferred: str | None = None) -> str:
    comp_files = snapshot.component_files()
    components = list(comp_files.keys())
    descriptors = load_or_build_component_descriptors(
        snapshot.project_root,
        snapshot=snapshot,
        persist=False,
    )
    if preferred:
        pref = preferred.strip()
        if pref in comp_files:
            return pref
        # allow short-form match (e.g., "gateway")
        for c in components:
            if pref.lower() in c.lower():
                return c

    q = (question or "").lower()
    mentions_tests = query_targets_tests(q)
    mentions_infra = query_targets_infra(q)
    scores = Counter()

    for comp in components:
        comp_low = comp.lower()
        if comp_low in q:
            scores[comp] += 10
        for token in comp_low.replace(":", "/").split("/"):
            if len(token) >= 3 and token in q:
                scores[comp] += 4

    for comp, descriptor in descriptors.items():
        search_text = descriptor_search_text(descriptor).lower()
        confidence = float(descriptor.get("confidence", 0.0) or 0.0)
        matched = 0
        for token in q.replace(":", " ").replace("/", " ").split():
            token = token.strip().lower()
            if len(token) < 4:
                continue
            if token in search_text:
                matched += 1
        if matched > 0:
            scores[comp] += matched * 3 + int(round(confidence * 3))

    if not mentions_tests:
        for comp in list(scores.keys()):
            if str(comp).endswith(":tests"):
                scores[comp] -= 6
    if not mentions_infra:
        for comp in list(scores.keys()):
            if is_infra_component(comp, descriptors.get(comp, {})):
                scores[comp] -= 7

    for path in snapshot.first_party_paths():
        low = path.lower()
        if low in q:
            scores[snapshot.component_for_path(path)] += 15
        elif any(token in low for token in q.split() if len(token) >= 3):
            scores[snapshot.component_for_path(path)] += 1

    if scores:
        ranked = scores.most_common()
        if not mentions_tests or not mentions_infra:
            for comp, _score in ranked:
                if not mentions_tests and str(comp).endswith(":tests"):
                    continue
                if not mentions_infra and is_infra_component(comp, descriptors.get(comp, {})):
                    continue
                return comp
        return ranked[0][0]

    # fallback: highest file-count component
    if components:
        filtered = list(components)
        if not mentions_tests:
            filtered = [comp for comp in filtered if not str(comp).endswith(":tests")]
        if not mentions_infra:
            filtered = [comp for comp in filtered if not is_infra_component(comp, descriptors.get(comp, {}))]
        if filtered:
            return max(filtered, key=lambda c: len(comp_files.get(c, [])))
        return max(components, key=lambda c: len(comp_files.get(c, [])))
    return "unknown"


def _component_dependency_edges(snapshot: HippoSnapshot, component: str) -> list[dict[str, Any]]:
    graph = build_component_graph(snapshot)
    out: list[dict[str, Any]] = []
    for item in component_neighbors(graph, component, limit=12):
        target_paths = item.get("target_paths", []) if isinstance(item, dict) else []
        first_path = target_paths[0] if isinstance(target_paths, list) and target_paths else ""
        out.append(
            {
                "target_component": str(item.get("target_component", "") or ""),
                "target_path": normalize_relpath(str(first_path or "")),
                "weight": int(item.get("weight", 0) or 0),
            }
        )
    return out


def answer_component_question(
    project_root: str | Path,
    question: str,
    *,
    component: str | None = None,
    llm_enabled: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    snapshot = HippoSnapshot.load(root)

    selected = _infer_component(snapshot, question, preferred=component)
    comp_files = snapshot.component_files().get(selected, [])

    sig_count = 0
    sample_symbols: list[str] = []
    for path in comp_files:
        sigs = snapshot.signatures_for_file(path)
        sig_count += len(sigs)
        for sig in sigs:
            name = str(sig.get("name", "")).strip()
            line = sig.get("line")
            if name and len(sample_symbols) < 12:
                sample_symbols.append(f"{path}:{line}:{name}")

    findings = [
        f for f in snapshot.first_party_findings() if snapshot.component_for_path(str(f.get("path", ""))) == selected
    ]
    hotspots = [h for h in aggregate_hotspots(findings, top_n=8)]
    deps = _component_dependency_edges(snapshot, selected)

    by_sev = Counter(str(f.get("severity", "info")).lower() for f in findings)
    by_dim = Counter(str(f.get("dimension", "other")).lower() for f in findings)

    answer_lines = [
        f"Component: {selected}",
        f"Files: {len(comp_files)}, signatures: {sig_count}",
        f"Findings: critical={by_sev.get('critical', 0)}, warning={by_sev.get('warning', 0)}, info={by_sev.get('info', 0)}",
    ]
    if hotspots:
        answer_lines.append("Top hotspot files:")
        for h in hotspots[:5]:
            answer_lines.append(
                f"- {h['path']} (critical={h['critical']}, warning={h['warning']}, score={h['score']})"
            )
    if deps:
        answer_lines.append("Top cross-component dependencies:")
        for edge in deps[:5]:
            answer_lines.append(
                f"- {edge['target_component']} via {edge['target_path']} (weight={edge['weight']})"
            )

    answer_lines.append("Suggested next step: fix critical hotspots first, then reduce branch density in top-2 hotspot files.")

    result = {
        "generated_at": utc_now_iso(),
        "question": question,
        "component": selected,
        "answer": "\n".join(answer_lines),
        "evidence": {
            "file_count": len(comp_files),
            "signature_count": sig_count,
            "sample_symbols": sample_symbols,
            "findings_by_severity": dict(by_sev),
            "findings_by_dimension": dict(by_dim),
            "hotspots": hotspots,
            "cross_component_edges": deps,
        },
    }
    if llm_enabled:
        payload = {
            "question": question,
            "component": selected,
            "evidence": {
                "findings_by_severity": dict(by_sev),
                "hotspots": hotspots[:6],
                "cross_component_edges": deps[:6],
                "sample_symbols": sample_symbols[:8],
            },
        }
        prompt = (
            "You are an architecture assistant answering component questions.\n"
            "Return strict JSON only with schema:\n"
            "{\n"
            '  "answer":"string",\n'
            '  "recommendations":["string"],\n'
            '  "confidence":0.0\n'
            "}\n\n"
            f"Input:\n{payload}"
        )
        llm_part = guard_llm_result(
            root,
            task="architect_component_qa",
            runner=lambda: complete_json(
                root,
                task="architect_component_qa",
                tier="strong",
                prompt=prompt,
                timeout_sec=16.0,
                max_tokens=900,
            ),
        )
        result["llm_enhancement"] = llm_part
    write_json(root / QA_REPORT_PATH, result)
    return result
