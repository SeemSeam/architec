from __future__ import annotations

from pathlib import Path

from architec.scoring_policy import (
    evaluate_full_score,
    evaluate_incremental_score,
    evaluate_overall_score,
    load_scoring_policy,
)


def test_full_score_uses_fixed_100_baseline_and_penalty() -> None:
    policy = load_scoring_policy(".")
    full = evaluate_full_score(
        summary={"by_severity": {"critical": 20, "warning": 40, "info": 10}},
        baseline_scores={"overall": 8.0},
        policy=policy,
    )

    assert full["mode"] == "full"
    assert 0.0 <= float(full["score"]) <= 100.0
    assert float(full["score"]) == 91.3
    assert full["grade"] in {"A", "B", "C", "D", "E"}
    assert "signals" in full
    assert full["signals"]["base_score"] == 100.0
    assert full["signals"]["base_score_source"] == "policy.full.base_score.fixed"


def test_full_score_supports_legacy_baseline_mode() -> None:
    policy = load_scoring_policy(".")
    policy["full"]["base_score"] = {"mode": "baseline_overall_x10"}
    full = evaluate_full_score(
        summary={"by_severity": {"critical": 20, "warning": 40, "info": 10}},
        baseline_scores={"overall": 8.0},
        policy=policy,
    )

    assert full["signals"]["base_score"] == 80.0
    assert full["signals"]["base_score_source"] == "baseline_scores.overall"
    assert float(full["score"]) == 71.3


def test_full_score_adaptive_thresholds_relax_with_penalty_pressure() -> None:
    policy = load_scoring_policy(".")
    full = evaluate_full_score(
        summary={"by_severity": {"critical": 500, "warning": 500, "info": 500}},
        baseline_scores={"overall": 8.0},
        policy=policy,
    )

    thresholds = full["thresholds"]
    assert thresholds["configured_pass_min"] == 78.0
    assert thresholds["configured_warn_min"] == 62.0
    assert round(float(thresholds["pass_min"]), 2) == 72.0
    assert round(float(thresholds["warn_min"]), 2) == 58.0
    assert full["recommendation"] == "block"


def test_full_score_ignores_grace_band_before_penalty() -> None:
    policy = load_scoring_policy(".")
    full = evaluate_full_score(
        summary={"by_severity": {"critical": 5, "warning": 20, "info": 25}},
        baseline_scores={"overall": 8.0},
        policy=policy,
    )

    assert float(full["signals"]["penalty"]["total"]) == 0.0
    assert float(full["score"]) == 100.0


def test_full_score_can_disable_adaptive_thresholds() -> None:
    policy = load_scoring_policy(".")
    policy["full"]["adaptive_thresholds"] = {"enabled": False}
    full = evaluate_full_score(
        summary={"by_severity": {"critical": 500, "warning": 500, "info": 500}},
        baseline_scores={"overall": 8.0},
        policy=policy,
    )

    thresholds = full["thresholds"]
    assert thresholds["pass_min"] == 78.0
    assert thresholds["warn_min"] == 62.0
    assert full["recommendation"] == "block"


def test_incremental_score_no_change_is_green() -> None:
    policy = load_scoring_policy(".")
    inc = evaluate_incremental_score(
        components=[],
        changed_file_total=0,
        policy=policy,
    )

    assert inc["mode"] == "no_change"
    assert inc["score"] == 100.0
    assert inc["recommendation"] == "approve"
    assert inc["gate_passed"] is True


def test_incremental_score_blocks_when_component_blocked() -> None:
    policy = load_scoring_policy(".")
    components = [
        {
            "component": "llm-proxy:ops/context",
            "score": 35.0,
            "recommendation": "block",
            "findings": {"critical": 4, "warning": 2, "info": 0},
            "churn": {"added": 40, "deleted": 20, "total": 60},
        },
        {
            "component": "hippocampus:nav",
            "score": 88.0,
            "recommendation": "approve",
            "findings": {"critical": 0, "warning": 1, "info": 0},
            "churn": {"added": 10, "deleted": 3, "total": 13},
        },
    ]
    inc = evaluate_incremental_score(
        components=components,
        changed_file_total=5,
        policy=policy,
    )

    assert inc["mode"] == "incremental"
    assert inc["recommendation"] == "block"
    assert inc["gate_passed"] is False
    assert int(inc["signals"]["blocked_components"]) >= 1


def test_incremental_score_macro_first_tolerates_single_local_blocker() -> None:
    policy = load_scoring_policy(".")
    components = [
        {
            "component": "llm-proxy:small-helper",
            "score": 39.0,
            "recommendation": "block",
            "findings": {"critical": 0, "warning": 1, "info": 0},
            "churn": {"added": 1, "deleted": 0, "total": 1},
        },
        {
            "component": "llm-proxy:ops/context",
            "score": 96.0,
            "recommendation": "approve",
            "findings": {"critical": 0, "warning": 0, "info": 0},
            "churn": {"added": 12, "deleted": 3, "total": 15},
            "trend": "up",
        },
    ]
    inc = evaluate_incremental_score(
        components=components,
        changed_file_total=2,
        policy=policy,
    )

    assert inc["mode"] == "incremental"
    assert int(inc["signals"]["blocked_components"]) == 1
    assert float(inc["signals"]["macro_progress_bonus"]) > 0.0
    assert inc["recommendation"] != "block"
    assert inc["gate_passed"] is True


def test_overall_score_does_not_escalate_low_signal_incremental_block() -> None:
    policy = load_scoring_policy(".")
    full = {
        "mode": "full",
        "score": 88.0,
        "recommendation": "approve",
    }
    incremental = {
        "mode": "incremental",
        "score": 72.0,
        "recommendation": "block",
        "signals": {"blocked_components": 1, "critical_total": 0},
    }
    overall = evaluate_overall_score(
        full_score=full,
        incremental_score=incremental,
        policy=policy,
    )

    assert overall["mode"] == "overall"
    assert overall["recommendation"] != "block"
    assert overall["gate_passed"] is True


def test_overall_score_escalates_incremental_block_when_risk_signals_high() -> None:
    policy = load_scoring_policy(".")
    full = {
        "mode": "full",
        "score": 88.0,
        "recommendation": "approve",
    }
    incremental = {
        "mode": "incremental",
        "score": 72.0,
        "recommendation": "block",
        "signals": {"blocked_components": 3, "critical_total": 4},
    }
    overall = evaluate_overall_score(
        full_score=full,
        incremental_score=incremental,
        policy=policy,
    )

    assert overall["mode"] == "overall"
    assert overall["recommendation"] == "block"
    assert overall["gate_passed"] is False


def test_overall_score_low_scope_reweight_reduces_incremental_impact() -> None:
    policy = load_scoring_policy(".")
    full = {
        "mode": "full",
        "score": 80.0,
        "recommendation": "approve",
    }
    incremental = {
        "mode": "incremental",
        "score": 10.0,
        "recommendation": "block",
        "signals": {
            "changed_file_total": 2,
            "component_total": 1,
            "blocked_components": 1,
            "critical_total": 0,
        },
    }
    overall = evaluate_overall_score(
        full_score=full,
        incremental_score=incremental,
        policy=policy,
    )

    assert overall["weights"]["full"] == 0.88
    assert overall["weights"]["incremental"] == 0.12
    assert overall["recommendation"] != "block"
    assert any(
        "low-scope incremental reweight applied" in reason
        for reason in overall.get("reasons", [])
    )


def test_load_scoring_policy_override(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    cfg_dir = root / ".architec"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "scoring-policy.json").write_text(
        '{"full":{"pass_min":90},"overall":{"weights":{"full":0.8,"incremental":0.2}}}',
        encoding="utf-8",
    )

    policy = load_scoring_policy(root)
    assert float(policy["full"]["pass_min"]) == 90.0
    assert float(policy["overall"]["weights"]["full"]) == 0.8
    assert float(policy["overall"]["weights"]["incremental"]) == 0.2
