from __future__ import annotations

from pathlib import Path
from typing import Any

from ..backend_llm import complete_json


def llm_feature_enhancement(
    project_root: Path,
    *,
    goal: str,
    target_components: list[dict[str, Any]],
    candidate_files: list[dict[str, Any]],
    related_hotspots: list[dict[str, Any]],
) -> dict[str, Any] | None:
    compact_targets = [
        {
            "component": t.get("component", ""),
            "score": t.get("score", 0),
        }
        for t in target_components[:5]
    ]
    compact_candidates = [
        {
            "path": c.get("path", ""),
            "component": c.get("component", ""),
            "score": c.get("score", 0),
        }
        for c in candidate_files[:10]
    ]
    compact_hotspots = [
        {
            "path": h.get("path", ""),
            "critical": h.get("critical", 0),
            "warning": h.get("warning", 0),
            "score": h.get("score", 0),
        }
        for h in related_hotspots[:8]
    ]
    payload = {
        "goal": goal,
        "target_components": compact_targets,
        "candidate_files": compact_candidates,
        "related_hotspots": compact_hotspots,
    }
    prompt = f"Input:\n{payload}"
    return complete_json(
        project_root,
        task="architect_feature",
        tier="strong",
        prompt=prompt,
        timeout_sec=25.0,
        max_tokens=800,
    )
