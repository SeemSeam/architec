from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ..backend_llm import complete_json
from ..descriptors.component_graph import build_component_graph, component_neighbors
from ..scoring.contract_engine import aggregate_hotspots
from ..integration.hippo_adapter import HippoSnapshot
from ..support.io_utils import normalize_relpath, utc_now_iso, write_json
from ..support.llm_guard import guard_llm_result
from ..integration.paths import QA_REPORT_PATH
from .component_qa_selection import infer_component


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


def _component_signature_evidence(
    snapshot: HippoSnapshot,
    comp_files: list[str],
) -> tuple[int, list[str]]:
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
    return sig_count, sample_symbols


def _component_findings(
    snapshot: HippoSnapshot,
    component: str,
) -> list[dict[str, Any]]:
    return [
        finding
        for finding in snapshot.first_party_findings()
        if snapshot.component_for_path(str(finding.get("path", ""))) == component
    ]


def _answer_lines(
    *,
    component: str,
    comp_files: list[str],
    sig_count: int,
    by_severity: Counter[str],
    hotspots: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
) -> list[str]:
    lines = [
        f"Component: {component}",
        f"Files: {len(comp_files)}, signatures: {sig_count}",
        (
            "Findings: "
            f"critical={by_severity.get('critical', 0)}, "
            f"warning={by_severity.get('warning', 0)}, "
            f"info={by_severity.get('info', 0)}"
        ),
    ]
    if hotspots:
        lines.append("Top hotspot files:")
        for hotspot in hotspots[:5]:
            lines.append(
                f"- {hotspot['path']} (critical={hotspot['critical']}, "
                f"warning={hotspot['warning']}, score={hotspot['score']})"
            )
    if dependencies:
        lines.append("Top cross-component dependencies:")
        for edge in dependencies[:5]:
            lines.append(
                f"- {edge['target_component']} via {edge['target_path']} (weight={edge['weight']})"
            )
    lines.append("Suggested next step: fix critical hotspots first, then reduce branch density in top-2 hotspot files.")
    return lines


def _qa_payload(
    *,
    question: str,
    component: str,
    by_severity: Counter[str],
    hotspots: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    sample_symbols: list[str],
) -> dict[str, Any]:
    return {
        "question": question,
        "component": component,
        "evidence": {
            "findings_by_severity": dict(by_severity),
            "hotspots": hotspots[:6],
            "cross_component_edges": dependencies[:6],
            "sample_symbols": sample_symbols[:8],
        },
    }


def _llm_enhancement(root: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    prompt = f"Input:\n{payload}"
    return guard_llm_result(
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


def answer_component_question(
    project_root: str | Path,
    question: str,
    *,
    component: str | None = None,
    llm_enabled: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    snapshot = HippoSnapshot.load(root)

    selected = infer_component(snapshot, question, preferred=component)
    comp_files = snapshot.component_files().get(selected, [])
    sig_count, sample_symbols = _component_signature_evidence(snapshot, comp_files)
    findings = _component_findings(snapshot, selected)
    hotspots = [h for h in aggregate_hotspots(findings, top_n=8)]
    deps = _component_dependency_edges(snapshot, selected)

    by_sev = Counter(str(f.get("severity", "info")).lower() for f in findings)
    by_dim = Counter(str(f.get("dimension", "other")).lower() for f in findings)
    answer_lines = _answer_lines(
        component=selected,
        comp_files=comp_files,
        sig_count=sig_count,
        by_severity=by_sev,
        hotspots=hotspots,
        dependencies=deps,
    )

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
        payload = _qa_payload(
            question=question,
            component=selected,
            by_severity=by_sev,
            hotspots=hotspots,
            dependencies=deps,
            sample_symbols=sample_symbols,
        )
        llm_part = _llm_enhancement(root, payload)
        result["llm_enhancement"] = llm_part
    write_json(root / QA_REPORT_PATH, result)
    return result
