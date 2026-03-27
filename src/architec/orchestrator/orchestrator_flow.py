from __future__ import annotations

from pathlib import Path
from typing import Any

from ..integration.hippo_adapter import HippoSnapshot
from .orchestrator_report import llm_orchestration_payload
from .orchestrator_timing import timed_step
from ..scoring.public import evaluate_overall_score


def timed_analysis_inputs(
    root: Path,
    *,
    goal: str,
    question: str,
    component: str | None,
    base: str | None,
    head: str | None,
    llm_enabled: bool,
    history_runner,
    feature_runner,
    score_runner,
    qa_runner,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    timings: dict[str, Any] = {}
    history, timings["history"] = timed_step(
        "history",
        lambda: history_runner(root, llm_enabled=llm_enabled),
    )
    feature, timings["feature"] = timed_step(
        "feature",
        lambda: feature_runner(root, goal=goal, llm_enabled=llm_enabled),
    )
    score, timings["score"] = timed_step(
        "score",
        lambda: score_runner(root, base=base, head=head, llm_enabled=llm_enabled),
    )
    qa, timings["qa"] = timed_step(
        "qa",
        lambda: qa_runner(
            root,
            question=question,
            component=component,
            llm_enabled=llm_enabled,
        ),
    )
    return history, feature, score, qa, timings


def governance_view(
    *,
    history: dict[str, Any],
    score: dict[str, Any],
    score_policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    full_score = (
        history.get("full_score", {})
        if isinstance(history.get("full_score"), dict)
        else {}
    )
    incremental_score = (
        score.get("incremental_score", {})
        if isinstance(score.get("incremental_score"), dict)
        else {}
    )
    overall_score = evaluate_overall_score(
        full_score=full_score,
        incremental_score=incremental_score,
        policy=score_policy,
    )
    return full_score, incremental_score, overall_score


def test_plan(
    *,
    snapshot: HippoSnapshot,
    batches: list[dict[str, Any]],
    root: Path,
    run_tests: bool,
    timings: dict[str, Any],
    collect_tests,
    build_commands,
    build_command_specs,
    run_commands,
) -> tuple[list[str], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
    tests = collect_tests(snapshot, batches)
    test_command_specs = build_command_specs(root, tests)
    test_commands = build_commands(root, tests)
    test_results: list[dict[str, Any]] = []
    if run_tests and test_commands:
        test_results, timings["tests"] = timed_step(
            "tests",
            lambda: run_commands(test_commands),
        )
        return tests, test_commands, test_command_specs, test_results
    timings["tests"] = {"label": "tests", "elapsed_sec": 0.0, "ok": True}
    return tests, test_commands, test_command_specs, test_results


def apply_llm_orchestration(
    *,
    root: Path,
    goal: str,
    question: str,
    batches: list[dict[str, Any]],
    test_commands: list[str],
    test_command_specs: list[dict[str, Any]],
    llm_enabled: bool,
    report: dict[str, Any],
    timings: dict[str, Any],
    cache_runner,
    llm_guard_runner,
    llm_enhancer,
) -> None:
    if not llm_enabled:
        timings["llm_orchestration"] = {
            "label": "llm_orchestration",
            "elapsed_sec": 0.0,
            "ok": True,
        }
        return
    llm_payload = llm_orchestration_payload(
        goal=goal,
        question=question,
        batches=batches,
        test_commands=test_commands,
        test_command_specs=test_command_specs,
    )
    llm_part, timings["llm_orchestration"] = timed_step(
        "llm_orchestration",
        lambda: cache_runner(
            root,
            namespace="architect_orchestrator",
            payload=llm_payload,
            runner=lambda: llm_guard_runner(
                root,
                task="architect_orchestrator",
                runner=lambda: llm_enhancer(
                    root,
                    goal=goal,
                    question=question,
                    batches=batches,
                    test_commands=test_commands,
                ),
            ),
        )[0],
    )
    report["llm_enhancement"] = llm_part
    timings["llm_orchestration"]["cache_hit"] = bool(
        isinstance(llm_part, dict) and llm_part.get("_cache_hit")
    )
