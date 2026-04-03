from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.analysis.public import run_analysis
from architec.gate.report import build_gate_result, load_baseline_snapshot, write_gate_artifacts


def run_gate(
    project_root: str | Path,
    *,
    progress=None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    baseline = load_baseline_snapshot(root)
    report = run_analysis(root, progress=progress)
    gate = build_gate_result(current_report=report, baseline=baseline)
    artifacts = write_gate_artifacts(
        root,
        {
            "meta": report.get("meta", {}),
            "scores": report.get("scores", {}),
            "cleanup": report.get("cleanup", {}),
            "gate": gate,
        },
    )

    result = dict(report)
    result["baseline"] = baseline
    result["gate"] = gate
    existing_artifacts = result.get("artifacts", {}) if isinstance(result.get("artifacts"), dict) else {}
    result["artifacts"] = {
        **existing_artifacts,
        **artifacts,
    }
    status_value = str(gate.get("status", "") or "fail")
    if status_value == "pass":
        status_text = "passed"
    elif status_value == "warn":
        status_text = "completed with warnings"
    else:
        status_text = "failed"
    failure_total = int(gate.get("failure_total", 0) or 0)
    warning_total = int(gate.get("warning_total", 0) or 0)
    result["summary"] = {
        "headline": (
            "Archi gate passed"
            if status_value == "pass"
            else ("Archi gate warned" if status_value == "warn" else "Archi gate failed")
        ),
        "executive_summary": (
            f"Compared current analysis against the recorded baseline and {status_text} "
            f"with {failure_total} failing checks and {warning_total} warning checks."
        ),
        "top_takeaways": [
            "Gate compares current full-analysis scores and cleanup totals against the stored baseline.",
            "Cleanup category regressions are now severity-aware: core legacy categories block, docs/config/prompt cleanup categories warn.",
            "Gate artifacts were written as standalone JSON and Markdown summaries.",
        ],
    }
    return result


__all__ = [
    "run_gate",
]
