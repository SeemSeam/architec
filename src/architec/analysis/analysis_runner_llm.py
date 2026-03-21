from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.analysis.analysis_cache import run_cached_analysis
from architec.backend_llm import complete_json
from architec.support.llm_guard import guard_llm_result


def llm_summary(root: Path, *, payload: dict[str, Any]) -> dict[str, Any] | None:
    prompt = f"Input:\n{payload}"
    result, _ = run_cached_analysis(
        root,
        namespace="architec_summary",
        payload=payload,
        runner=lambda: guard_llm_result(
            root,
            task="architec_summary",
            runner=lambda: complete_json(
                root,
                task="architec_summary",
                tier="strong",
                prompt=prompt,
                timeout_sec=30.0,
                max_tokens=900,
                required=True,
            ),
        ),
    )
    return result if isinstance(result, dict) else None


def run_diff_analysis(root: Path, *, diff: bool, base: str, head: str, runner) -> dict[str, Any]:
    if not diff:
        return {}
    return runner(root, base=base or None, head=head or None, llm_enabled=True)


def run_goal_analysis(root: Path, *, goal: str, runner) -> dict[str, Any]:
    if not goal:
        return {}
    return runner(root, goal=goal, llm_enabled=True)
