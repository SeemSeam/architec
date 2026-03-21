from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.backend_llm import complete_json


def llm_scoring_enhancement(
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
    prompt = f"Input:\n{payload}"
    return complete_json(
        project_root,
        task="architect_component_scoring",
        tier="weak",
        prompt=prompt,
        timeout_sec=20.0,
        max_tokens=500,
    )
