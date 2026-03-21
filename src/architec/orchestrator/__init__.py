from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from ..reporting.architecture_report_md import (
    ARCHITECTURE_REPORT_MD_PATH,
    write_architecture_report_markdown,
)
from ..descriptors.public import load_or_build_component_descriptors
from .component_qa import answer_component_question
from ..scoring.component_scoring import score_changed_components
from ..feature.feature_advisor import suggest_feature_architecture
from ..integration.hippo_adapter import HippoSnapshot
from ..analysis.history_analyzer import analyze_history_and_iterate
from ..analysis.hotspot_digest import HOTSPOT_DIGEST_PATH, build_hotspot_digest
from ..support.io_utils import utc_now_iso, write_json
from ..analysis.analysis_cache import run_cached_analysis
from ..support.llm_guard import guard_llm_result
from .orchestrator_flow import (
    apply_llm_orchestration,
    governance_view,
    test_plan,
    timed_analysis_inputs,
)
from .orchestrator_batches import pick_change_batches
from .orchestrator_llm import llm_orchestration_enhancement
from .orchestrator_report import (
    build_orchestration_report,
    runtime_summary,
)
from .orchestrator_test_plan import (
    _build_test_commands,
    _collect_test_candidates,
    _is_valid_pytest_target,
    _run_test_commands,
)
from .orchestrator_timing import timed_step
from ..scoring.public import load_scoring_policy


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
    snapshot = HippoSnapshot.load(root)
    descriptors = load_or_build_component_descriptors(root, snapshot=snapshot, persist=False)
    history, feature, score, qa, timings = timed_analysis_inputs(
        root,
        goal=goal,
        question=question,
        component=component,
        base=base,
        head=head,
        llm_enabled=llm_enabled,
        history_runner=analyze_history_and_iterate,
        feature_runner=suggest_feature_architecture,
        score_runner=score_changed_components,
        qa_runner=answer_component_question,
    )
    full_score, incremental_score, overall_score = governance_view(
        history=history,
        score=score,
        score_policy=score_policy,
    )

    batches = pick_change_batches(
        history=history,
        feature=feature,
        score=score,
        descriptors=descriptors,
        qa_component=str(qa.get("component", "") or ""),
        goal=goal,
    )
    tests, test_commands, test_results = test_plan(
        snapshot=snapshot,
        batches=batches,
        root=root,
        run_tests=run_tests,
        timings=timings,
        collect_tests=_collect_test_candidates,
        build_commands=_build_test_commands,
        run_commands=_run_test_commands,
    )
    report = build_orchestration_report(
        root=root,
        generated_at=utc_now_iso(),
        goal=goal,
        question=question,
        component_hint=component or "",
        history=history,
        feature=feature,
        score=score,
        qa=qa,
        full_score=full_score,
        incremental_score=incremental_score,
        overall_score=overall_score,
        batches=batches,
        tests=tests,
        test_commands=test_commands,
        run_tests=run_tests,
        test_results=test_results,
    )
    apply_llm_orchestration(
        root=root,
        goal=goal,
        question=question,
        batches=batches,
        test_commands=test_commands,
        llm_enabled=llm_enabled,
        report=report,
        timings=timings,
        cache_runner=run_cached_analysis,
        llm_guard_runner=guard_llm_result,
        llm_enhancer=_llm_orchestration_enhancement,
    )

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
    report["runtime"] = runtime_summary(timings)

    write_json(root / ORCHESTRATION_REPORT_PATH, report)
    return report


__all__ = [
    "ARCHITECTURE_REPORT_MD_PATH",
    "HOTSPOT_DIGEST_PATH",
    "ORCHESTRATION_REPORT_PATH",
    "_build_test_commands",
    "_collect_test_candidates",
    "_is_valid_pytest_target",
    "_run_test_commands",
    "_timed_step",
    "answer_component_question",
    "orchestrate_analysis_modify_test",
    "pick_change_batches",
    "score_changed_components",
    "suggest_feature_architecture",
]
