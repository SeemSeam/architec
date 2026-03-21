from __future__ import annotations

from pathlib import Path
from typing import Any

from ..reporting.architecture_report_md import ARCHITECTURE_REPORT_MD_PATH
from ..analysis.hotspot_digest import HOTSPOT_DIGEST_PATH
from ..integration.resource_paths import resolve_config_file


def llm_orchestration_payload(
    *,
    goal: str,
    question: str,
    batches: list[dict[str, Any]],
    test_commands: list[str],
) -> dict[str, Any]:
    return {
        "goal": goal,
        "question": question,
        "batches": [
            {
                "batch": batch.get("batch"),
                "component": batch.get("component"),
                "priority": batch.get("priority"),
                "focus_files": batch.get("focus_files", [])[:6],
            }
            for batch in batches[:4]
        ],
        "test_commands": test_commands[:3],
    }


def build_orchestration_report(
    *,
    root: Path,
    generated_at: str,
    goal: str,
    question: str,
    component_hint: str,
    history: dict[str, Any],
    feature: dict[str, Any],
    score: dict[str, Any],
    qa: dict[str, Any],
    full_score: dict[str, Any],
    incremental_score: dict[str, Any],
    overall_score: dict[str, Any],
    batches: list[dict[str, Any]],
    tests: list[str],
    test_commands: list[str],
    run_tests: bool,
    test_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "generated_at": generated_at,
        "goal": goal,
        "question": question,
        "component_hint": component_hint,
        "analysis": {
            "history_summary": history.get("summary", {}),
            "full_score": full_score,
            "feature_targets": feature.get("target_components", []),
            "score_summary": score.get("summary", {}),
            "incremental_score": incremental_score,
            "qa_component": qa.get("component", ""),
        },
        "governance": {
            "full_score": full_score,
            "incremental_score": incremental_score,
            "overall_score": overall_score,
        },
        "change_batches": batches,
        "test_plan": {
            "selected_tests": tests,
            "commands": test_commands,
            "executed": bool(run_tests),
            "results": test_results,
        },
        "artifacts": {
            "history": str(root / ".architec/architec-history-report.json"),
            "feature": str(root / ".architec/architec-feature-suggestion.json"),
            "score": str(root / ".architec/architec-component-score.json"),
            "qa": str(root / ".architec/architec-component-qa.json"),
            "hotspot_minimal": str(root / HOTSPOT_DIGEST_PATH),
            "architecture_report_md": str(root / ARCHITECTURE_REPORT_MD_PATH),
        },
        "policy": {
            "coordination": "analyze -> change-batch -> targeted-test -> next batch",
            "gate": "do not proceed to next high-risk batch when tests fail",
            "dual_scoring_policy": str(resolve_config_file(root, "scoring-policy.json")),
        },
    }


def runtime_summary(timings: dict[str, Any]) -> dict[str, Any]:
    slowest = (
        max(timings.values(), key=lambda item: float(item.get("elapsed_sec", 0.0)))
        if timings
        else {}
    )
    return {"timings": timings, "slowest_step": slowest}
