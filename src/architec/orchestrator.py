from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from .analysis_cache import run_cached_analysis
from .architecture_report_md import (
    ARCHITECTURE_REPORT_MD_PATH,
    write_architecture_report_markdown,
)
from .component_descriptors import load_or_build_component_descriptors
from .component_qa import answer_component_question
from .component_scoring import score_changed_components
from .feature_advisor import suggest_feature_architecture
from .hippo_adapter import HippoSnapshot
from .history_analyzer import analyze_history_and_iterate
from .hotspot_digest import HOTSPOT_DIGEST_PATH, build_hotspot_digest
from .io_utils import utc_now_iso, write_json
from .llm_guard import guard_llm_result
from .orchestrator_batches import pick_change_batches
from .orchestrator_llm import llm_orchestration_enhancement
from .orchestrator_timing import timed_step
from .orchestrator_test_plan import (
    _build_test_commands,
    _collect_test_candidates,
    _is_valid_pytest_target,
    _run_test_commands,
)
from .resource_paths import resolve_config_file
from .scoring_policy import evaluate_overall_score, load_scoring_policy


ORCHESTRATION_REPORT_PATH = Path(".architec/architec-orchestration-report.json")


_timed_step = timed_step
_llm_orchestration_enhancement = llm_orchestration_enhancement


def orchestrate_analysis_modify_test(
    project_root: str | Path,
    *,
    goal: str,
    question: str,
    component: str | None = None,
    base: str | None = None,
    head: str | None = None,
    llm_enabled: bool = True,
    run_tests: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    score_policy = load_scoring_policy(root)
    timings: dict[str, Any] = {}
    snapshot = HippoSnapshot.load(root)
    descriptors = load_or_build_component_descriptors(root, snapshot=snapshot, persist=False)

    history, timings["history"] = _timed_step(
        "history",
        lambda: analyze_history_and_iterate(root, llm_enabled=llm_enabled),
    )
    feature, timings["feature"] = _timed_step(
        "feature",
        lambda: suggest_feature_architecture(root, goal=goal, llm_enabled=llm_enabled),
    )
    score, timings["score"] = _timed_step(
        "score",
        lambda: score_changed_components(root, base=base, head=head, llm_enabled=llm_enabled),
    )
    qa, timings["qa"] = _timed_step(
        "qa",
        lambda: answer_component_question(
            root,
            question=question,
            component=component,
            llm_enabled=llm_enabled,
        ),
    )
    full_score = history.get("full_score", {}) if isinstance(history.get("full_score"), dict) else {}
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

    batches = pick_change_batches(
        history=history,
        feature=feature,
        score=score,
        descriptors=descriptors,
        qa_component=str(qa.get("component", "") or ""),
        goal=goal,
    )
    tests = _collect_test_candidates(snapshot, batches)
    test_commands = _build_test_commands(root, tests)

    test_results: list[dict[str, Any]] = []
    if run_tests and test_commands:
        test_results, timings["tests"] = _timed_step(
            "tests",
            lambda: _run_test_commands(test_commands),
        )
    else:
        timings["tests"] = {"label": "tests", "elapsed_sec": 0.0, "ok": True}

    report = {
        "generated_at": utc_now_iso(),
        "goal": goal,
        "question": question,
        "component_hint": component or "",
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

    if llm_enabled:
        llm_payload = {
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
        llm_part, timings["llm_orchestration"] = _timed_step(
            "llm_orchestration",
            lambda: run_cached_analysis(
                root,
                namespace="architect_orchestrator",
                payload=llm_payload,
                runner=lambda: guard_llm_result(
                    root,
                    task="architect_orchestrator",
                    runner=lambda: _llm_orchestration_enhancement(
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
    else:
        timings["llm_orchestration"] = {
            "label": "llm_orchestration",
            "elapsed_sec": 0.0,
            "ok": True,
        }

    hotspot_digest = build_hotspot_digest(
        root,
        history=history,
        score=score,
        batches=batches,
        governance={
            "full": full_score.get("score", 0.0),
            "incremental": incremental_score.get("score", 0.0),
            "overall": overall_score.get("score", 0.0),
        },
    )
    report["hotspot_minimal"] = {
        "topk": int(hotspot_digest.get("topk", 0) or 0),
        "count": len(hotspot_digest.get("items", []) or []),
        "path": str(root / HOTSPOT_DIGEST_PATH),
    }
    report["architecture_report"], timings["architecture_report"] = _timed_step(
        "architecture_report",
        lambda: write_architecture_report_markdown(
            root,
            goal=goal,
            question=question,
            governance={
                "full": full_score.get("score", 0.0),
                "incremental": incremental_score.get("score", 0.0),
                "overall": overall_score.get("score", 0.0),
            },
            hotspot_digest=hotspot_digest,
            batches=batches,
            feature=feature,
            qa=qa,
            llm_enabled=llm_enabled,
        ),
    )
    report["runtime"] = {
        "timings": timings,
        "slowest_step": max(
            timings.values(),
            key=lambda item: float(item.get("elapsed_sec", 0.0)),
        )
        if timings
        else {},
    }

    write_json(root / ORCHESTRATION_REPORT_PATH, report)
    return report
