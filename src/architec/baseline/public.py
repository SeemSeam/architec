from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.analysis.public import run_analysis
from architec.baseline.report import build_baseline_snapshot, write_baseline_artifacts


def run_baseline(
    project_root: str | Path,
    *,
    progress=None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    report = run_analysis(root, progress=progress)
    baseline = build_baseline_snapshot(report)
    artifacts = write_baseline_artifacts(root, baseline)

    result = dict(report)
    result["baseline"] = baseline
    existing_artifacts = result.get("artifacts", {}) if isinstance(result.get("artifacts"), dict) else {}
    result["artifacts"] = {
        **existing_artifacts,
        **artifacts,
    }
    result["summary"] = {
        "headline": "Archi baseline captured",
        "executive_summary": (
            f"Captured baseline at overall {result.get('scores', {}).get('overall', 0.0)} "
            f"with {result.get('cleanup', {}).get('candidate_total', 0)} cleanup candidates."
        ),
        "top_takeaways": [
            "Baseline snapshot written for current full analysis outputs.",
            "Top hotspots, cleanup categories, and topology summary were frozen into dedicated baseline artifacts.",
            "Future regression checks can compare against this baseline without rebuilding cleanup heuristics.",
        ],
    }
    return result


__all__ = [
    "run_baseline",
]
