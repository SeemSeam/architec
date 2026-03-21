from __future__ import annotations

from pathlib import Path
from typing import Any

from ..backend_llm import complete_json


def llm_orchestration_enhancement(
    root: Path,
    *,
    goal: str,
    question: str,
    batches: list[dict[str, Any]],
    test_commands: list[str],
) -> dict[str, Any] | None:
    payload = {
        "goal": goal,
        "question": question,
        "batches": [
            {
                "batch": b.get("batch"),
                "component": b.get("component"),
                "priority": b.get("priority"),
                "focus_files": b.get("focus_files", [])[:6],
            }
            for b in batches[:4]
        ],
        "test_commands": test_commands[:3],
    }
    prompt = f"Input:\n{payload}"
    return complete_json(
        root,
        task="architect_orchestrator",
        tier="strong",
        prompt=prompt,
        timeout_sec=25.0,
        max_tokens=900,
    )
