from __future__ import annotations

from pathlib import Path
from typing import Any

from .backend_llm import complete_json


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
    prompt = (
        "You are an architecture program coordinator. "
        "Create an execution plan across analysis, code modification, and testing.\n"
        "Return strict JSON only with schema:\n"
        "{\n"
        '  "program_summary":"string",\n'
        '  "execution_order":[{"batch":"string","objective":"string","risk":"low|medium|high"}],\n'
        '  "code_change_checklist":["string"],\n'
        '  "test_gate":["string"],\n'
        '  "rollback_guard":["string"]\n'
        "}\n\n"
        f"Input:\n{payload}"
    )
    return complete_json(
        root,
        task="architect_orchestrator",
        tier="strong",
        prompt=prompt,
        timeout_sec=25.0,
        max_tokens=900,
    )
