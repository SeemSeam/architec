from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import architec.cli as cli
import pytest


def _code_review_result(review_type: str) -> dict[str, object]:
    headline = (
        "No new architecture concerns were identified in the selected diff."
        if review_type == "diff"
        else "Full code review complete"
    )
    concerns = []
    signals = []
    summary = {
        "headline": headline,
        "concern_total": 0,
        "top_concern_total": 0,
        "concern_limit": 5,
        "signal_kinds": [],
    }
    if review_type != "diff":
        summary = {
            "headline": headline,
            "concern_total": 1,
            "top_concern_total": 1,
            "concern_limit": 5,
            "signal_kinds": ["cleanup"],
        }
        signals = [
            {
                "kind": "cleanup",
                "summary": "1 cleanup candidates; 1 marked for review.",
                "metrics": {"candidate_total": 1, "review_required_total": 1},
            }
        ]
        concerns = [
            {
                "concern_id": "code-review:cleanup:abc123def456",
                "kind": "cleanup",
                "level": "caution",
                "confidence": 0.82,
                "location": {"path": "src/legacy.py", "line": 0, "symbol": "", "symbol_kind": "module"},
                "root_cause": "Cleanup candidate categorized as legacy_impl.",
                "evidence": ["cleanup.category=legacy_impl"],
                "blast_radius": ["src/legacy.py"],
                "next_steps_hint": "Review whether the file is still owned and intentionally retained.",
            }
        ]
    return {
        "mode": "code_review",
        "review_type": review_type,
        "scores": {"overall": 82.0},
        "summary": summary,
        "findings": [],
        "signals": signals,
        "evidence": [],
        "concerns": concerns,
        "artifacts": {"analysis_json": "/tmp/.architec/architec-analysis.json"},
    }


def _assert_advisory_only(payload: str) -> None:
    lowered = payload.lower()
    assert "pass" not in lowered
    assert "fail" not in lowered
    assert "block" not in lowered
    assert "verdict" not in lowered
    assert "must-fix" not in lowered


def test_build_parser_accepts_trailing_path():
    parser = cli.build_parser()
    assert parser.prog == "archi"
    args = parser.parse_args(["--diff", "--base", "main", "--head", "HEAD", "."])
    assert args.diff is True
    assert args.full is False
    assert args.base == "main"
    assert args.head == "HEAD"
    assert args.path == "."


def test_build_parser_accepts_full_review_flag():
    parser = cli.build_parser()

    args = parser.parse_args(["--full", "."])

    assert args.full is True
    assert args.diff is False
    assert args.path == "."


def test_build_parser_accepts_advice_feedback_for_full_review():
    parser = cli.build_parser()

    args = parser.parse_args(["--full", "--advice-feedback", "feedback.json", "."])

    assert args.advice_feedback == "feedback.json"


def test_build_parser_help_mentions_self_manage_commands() -> None:
    help_text = cli.build_parser().format_help()

    assert "archi update" in help_text
    assert "archi uninstall" in help_text


def test_build_parser_help_uses_chinese_locale(monkeypatch) -> None:
    monkeypatch.setenv("ARCHITEC_LANG", "zh")

    help_text = cli.build_parser().format_help()

    assert "Archi 架构分析 CLI" in help_text
    assert "位置参数:" in help_text
    assert "选项:" in help_text
    assert "显示当前 CLI 版本和最新发布状态" in help_text
    assert "显示此帮助信息并退出" in help_text


def test_build_parser_rejects_removed_goal_flag(capsys) -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--goal", "review", "."])

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "unrecognized arguments: --goal" in captured.err


def test_build_parser_error_uses_chinese_locale(monkeypatch, capsys) -> None:
    monkeypatch.setenv("ARCHITEC_LANG", "zh")
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--goal", "review", "."])

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "错误: 无法识别的参数：--goal" in captured.err


def test_build_parser_help_omits_goal() -> None:
    help_text = cli.build_parser().format_help().lower()

    assert "--goal" not in help_text


def test_build_parser_help_keeps_public_parameter_surface_small() -> None:
    help_text = cli.build_parser().format_help()

    assert "--full" in help_text
    assert "--refresh-from-hippos" in help_text
    assert "--check" in help_text
    assert "--allow-static" in help_text
    assert "--out" in help_text

    for hidden in (
        "--diff",
        "--base",
        "--head",
        "--plan-review",
        "--risk-context",
        "--advice-feedback",
        "--component",
        "--format",
        "--open-browser",
        "--skip-auth",
    ):
        assert hidden not in help_text


def test_required_llm_checks_no_longer_include_goal_feature_check() -> None:
    full_checks = cli._required_llm_checks(diff=False)
    diff_checks = cli._required_llm_checks(diff=True)

    assert ("architect_feature", "strong") not in full_checks
    assert ("architect_feature", "strong") not in diff_checks
    assert ("architect_component_scoring", "weak") not in full_checks
    assert ("architect_component_scoring", "weak") not in diff_checks
    assert full_checks == diff_checks


def test_build_plan_review_parser_accepts_plan_and_project_root():
    parser = cli.build_plan_review_parser()
    assert parser.prog == "archi plan-review"
    args = parser.parse_args(["--out", "/tmp/plan.json", "--project-root", "/repo", "plan.md"])
    assert args.out == "/tmp/plan.json"
    assert args.project_root == "/repo"
    assert args.plan == "plan.md"


def test_build_code_review_parser_accepts_full_and_trailing_path():
    parser = cli.build_code_review_parser()
    assert parser.prog == "archi code-review"
    args = parser.parse_args(
        ["--full", "--allow-static", "--out", "/tmp/review.json", "--risk-context", "risk.json", "."]
    )
    assert args.full is True
    assert args.allow_static is True
    assert args.diff is False
    assert args.since == ""
    assert args.out == "/tmp/review.json"
    assert args.risk_context == "risk.json"
    assert args.base == ""
    assert args.head == ""
    assert args.path == "."


def test_build_code_review_parser_accepts_diff_range_and_trailing_path():
    parser = cli.build_code_review_parser()
    args = parser.parse_args(
        ["--diff", "--base", "main", "--head", "HEAD", "--plan-review", "plan.json", "."]
    )
    assert args.full is False
    assert args.diff is True
    assert args.since == ""
    assert args.base == "main"
    assert args.head == "HEAD"
    assert args.plan_review == "plan.json"
    assert args.path == "."


def test_build_code_review_parser_accepts_since_ref_and_trailing_path():
    parser = cli.build_code_review_parser()
    args = parser.parse_args(["--since", "main", "--plan-review", "plan.json", "."])
    assert args.full is False
    assert args.diff is False
    assert args.since == "main"
    assert args.base == ""
    assert args.head == ""
    assert args.plan_review == "plan.json"
    assert args.path == "."


def test_validate_code_review_rejects_plan_review_with_full(capsys):
    parser = cli.build_code_review_parser()
    args = parser.parse_args(["--full", "--plan-review", "plan.json", "."])

    assert cli._validate_code_review_args(args) == 2
    captured = capsys.readouterr()
    assert "--plan-review requires --diff or --since" in captured.err


def test_build_parser_accepts_incremental_plan_review_and_rejects_full(capsys):
    parser = cli.build_parser()
    args = parser.parse_args(["--diff", "--plan-review", "plan.json", "."])
    assert args.plan_review == "plan.json"
    assert args.diff is True

    bare = parser.parse_args(["--plan-review", "plan.json", "."])
    assert cli._validate_args(bare) is None

    invalid = parser.parse_args(["--full", "--plan-review", "plan.json", "."])
    assert cli._validate_args(invalid) == 2
    captured = capsys.readouterr()
    assert "--plan-review requires incremental review" in captured.err


def test_main_top_level_check_rejects_plan_review_before_runtime_work(monkeypatch, tmp_path, capsys):
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "--check", "--diff", "--plan-review", str(plan_review), str(tmp_path)],
    )
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm should not run"))
    monkeypatch.setattr(cli, "run_code_review_diff", lambda *args, **kwargs: pytest.fail("diff should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--plan-review cannot be used with --check" in captured.err


def test_main_top_level_check_rejects_risk_context_before_runtime_work(monkeypatch, tmp_path, capsys):
    risk_context = tmp_path / "risk.json"
    risk_context.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["archi", "--check", "--risk-context", str(risk_context), str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm should not run"))
    monkeypatch.setattr(cli, "run_code_review_full", lambda *args, **kwargs: pytest.fail("full should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--risk-context cannot be used with --check" in captured.err


def test_build_status_parser_accepts_advisory_modes():
    parser = cli.build_status_parser()
    assert parser.prog == "archi status"
    trend = parser.parse_args(["--trend", "."])
    assert trend.trend is True
    assert trend.snapshot is False
    assert trend.path == "."
    snapshot = parser.parse_args(["--snapshot", "--out", "/tmp/status.json", "."])
    assert snapshot.snapshot is True
    assert snapshot.out == "/tmp/status.json"


def test_build_fix_advice_parser_accepts_review_and_focus_options():
    parser = cli.build_fix_advice_parser()
    assert parser.prog == "archi fix-advice"
    args = parser.parse_args([
        "--review",
        "review.json",
        "--focus-file",
        "src/core.py",
        "--focus-kind",
        "hotspot",
        "--concern-id",
        "code-review:hotspot:1",
        "--advice-feedback",
        "feedback.json",
        "--out",
        "/tmp/fix.json",
    ])
    assert args.review == "review.json"
    assert args.focus_file == "src/core.py"
    assert args.focus_kind == "hotspot"
    assert args.concern_id == "code-review:hotspot:1"
    assert args.advice_feedback == "feedback.json"
    assert args.out == "/tmp/fix.json"


def test_build_fix_advice_parser_accepts_for_compat_alias():
    parser = cli.build_fix_advice_parser()

    args = parser.parse_args(["--for", "review.json"])

    assert args.review == "review.json"


def test_build_fix_advice_parser_rejects_review_and_for_together(capsys):
    parser = cli.build_fix_advice_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--review", "new.json", "--for", "old.json"])

    assert exc.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_build_fix_advice_parser_help_marks_for_as_compat_alias():
    help_text = cli.build_fix_advice_parser().format_help()

    assert "--review" in help_text
    assert "compatibility alias for --review" in help_text


def test_main_rejects_base_without_diff(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--base", "main"])
    assert cli.main() == 2
    assert "--base/--head require --diff" in capsys.readouterr().err


def test_main_rejects_advice_feedback_with_check(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--check", "--advice-feedback", "feedback.json"])

    assert cli.main() == 2

    assert "--advice-feedback cannot be used with --check" in capsys.readouterr().err


def test_main_rejects_advice_feedback_with_diff(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--diff", "--advice-feedback", "feedback.json"])

    assert cli.main() == 2

    assert "--advice-feedback currently requires --full" in capsys.readouterr().err


def test_main_code_review_rejects_base_without_diff(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--full", "--base", "main", "."])
    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--base/--head require --diff" in captured.err


def test_main_code_review_rejects_since_with_base(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--since", "main", "--base", "dev", "."])
    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--base/--head require --diff" in captured.err


def test_main_code_review_rejects_advice_feedback_with_diff(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--diff", "--advice-feedback", "feedback.json", "."])

    assert cli.main() == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--advice-feedback currently requires --full" in captured.err


def test_main_version_exits_before_auth(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["archi", "--version"])
    monkeypatch.setattr(cli, "print_version_status", lambda: 0)
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm check should not run"))

    assert cli.main() == 0


def test_ensure_bundle_auto_refreshes_when_bundle_missing(monkeypatch):
    args = SimpleNamespace(path=".", refresh_from_hippo=False)
    calls: list[str] = []

    def fake_inspect_bundle(path):
        calls.append(f"inspect:{path}")
        return SimpleNamespace(missing_files=[".hippocampus/architect-metrics.json"], stale_reasons=[], ok=False)

    def fake_refresh(path):
        calls.append(f"refresh:{path}")
        return {"ok": True, "refreshed": str(path)}

    monkeypatch.setattr(cli, "inspect_bundle", fake_inspect_bundle)
    monkeypatch.setattr(cli, "refresh_bundle_from_hippo", fake_refresh)

    result = cli._ensure_bundle(args)

    assert result == {"ok": True, "refreshed": "."}
    assert calls == ["inspect:.", "refresh:."]


def test_ensure_bundle_auto_refreshes_when_bundle_stale(monkeypatch):
    args = SimpleNamespace(path=".", refresh_from_hippo=False)
    calls: list[str] = []

    def fake_inspect_bundle(path):
        calls.append(f"inspect:{path}")
        return SimpleNamespace(
            missing_files=[],
            stale_reasons=["architect-metrics.json does not match current Hippo bundle"],
            ok=False,
        )

    def fake_refresh(path):
        calls.append(f"refresh:{path}")
        return {"ok": True, "refreshed": str(path)}

    monkeypatch.setattr(cli, "inspect_bundle", fake_inspect_bundle)
    monkeypatch.setattr(cli, "refresh_bundle_from_hippo", fake_refresh)

    result = cli._ensure_bundle(args)

    assert result == {"ok": True, "refreshed": "."}
    assert calls == ["inspect:.", "refresh:."]


def test_main_check_auto_refreshes_missing_bundle(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--check", "."])

    def fake_inspect_bundle(path):
        return SimpleNamespace(missing_files=["missing"], stale_reasons=[], ok=False)

    monkeypatch.setattr(cli, "inspect_bundle", fake_inspect_bundle)
    monkeypatch.setattr(
        cli,
        "refresh_bundle_from_hippo",
        lambda path: {"ok": True, "project_root": path, "steps": ["hippo"]},
    )
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda path, *, checks: None)

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "Hippos bundle missing, refreshing via hippos" in captured.err
    out = captured.out
    assert "Archi preflight OK" in out
    assert "Hippos bundle: refreshed" in out


def test_main_check_auto_refreshes_stale_bundle(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--check", "."])
    monkeypatch.setattr(
        cli,
        "inspect_bundle",
        lambda path: SimpleNamespace(
            missing_files=[],
            stale_reasons=["architect-metrics.json missing bundle_fingerprint"],
            ok=False,
        ),
    )
    monkeypatch.setattr(
        cli,
        "refresh_bundle_from_hippo",
        lambda path: {"ok": True, "project_root": path, "steps": ["hippo"]},
    )
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda path, *, checks: None)

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "Hippos bundle stale, refreshing via hippos" in captured.err
    assert "Archi preflight OK" in captured.out


def test_main_bare_archi_routes_to_incremental_llm_without_bundle_refresh(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = _code_review_result("diff")
    result["summary"]["analysis_mode"] = "incremental_llm"

    monkeypatch.setattr(sys, "argv", ["archi", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not refresh for bare archi"))
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(cli, "run_code_review_full", lambda *args, **kwargs: pytest.fail("full should not run"))
    monkeypatch.setattr(
        cli,
        "run_code_review_incremental_llm",
        lambda path, *, base="", head="", progress=None: calls.append(
            ("review_incremental", path, base, head, progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "archi [3/3] running incremental LLM code review" in captured.err
    assert "No new architecture concerns were identified in the selected diff." in captured.out
    assert calls[0] == ("llm", str(tmp_path), (("architec_summary", "strong"),))
    assert calls[1] == ("review_incremental", str(tmp_path), "", "", True)


def test_main_full_flag_passes_advice_feedback_path(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = _code_review_result("full")
    feedback = tmp_path / "feedback.json"
    feedback.write_text(json.dumps({"items": []}), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["archi", "--full", "--advice-feedback", str(feedback), str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_full",
        lambda path, *, advice_feedback_path=None, progress=None: calls.append(
            ("review_full", path, str(advice_feedback_path), progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    capsys.readouterr()
    assert calls[2] == ("review_full", str(tmp_path), str(feedback), True)


def test_main_legacy_diff_alias_routes_to_incremental_llm_args(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = _code_review_result("diff")

    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "--diff", "--base", "main", "--head", "HEAD", str(tmp_path)],
    )
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not refresh for incremental alias"))
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(cli, "run_code_review_full", lambda *args, **kwargs: pytest.fail("full should not run"))
    monkeypatch.setattr(cli, "run_code_review_diff", lambda *args, **kwargs: pytest.fail("direct diff should not run"))
    monkeypatch.setattr(
        cli,
        "run_code_review_incremental_llm",
        lambda path, *, base="", head="", progress=None: calls.append(
            ("review_incremental", path, base, head, progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "archi [3/3] running incremental LLM code review" in captured.err
    assert "No new architecture concerns were identified in the selected diff." in captured.out
    assert calls[0] == ("llm", str(tmp_path), (("architec_summary", "strong"),))
    assert calls[1] == ("review_incremental", str(tmp_path), "main", "HEAD", True)


def test_main_top_level_diff_passes_plan_review_path(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = _code_review_result("diff")
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "--diff", "--plan-review", str(plan_review), str(tmp_path)],
    )
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not refresh for incremental alias"))
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_incremental_llm",
        lambda path, *, base="", head="", plan_review_path=None, progress=None: calls.append(
            ("review_incremental", path, base, head, str(plan_review_path), progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    capsys.readouterr()
    assert calls[1] == ("review_incremental", str(tmp_path), "", "", str(plan_review), True)


def test_main_legacy_check_still_uses_preflight_result(monkeypatch, tmp_path, capsys):
    calls: list[object] = []

    monkeypatch.setattr(sys, "argv", ["archi", "--check", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(cli, "run_code_review_full", lambda *args, **kwargs: pytest.fail("full should not run"))
    monkeypatch.setattr(cli, "run_code_review_diff", lambda *args, **kwargs: pytest.fail("diff should not run"))

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "archi [3/3] preflight complete" in captured.err
    assert "Archi preflight OK" in captured.out
    assert calls[0] == ("bundle", str(tmp_path))
    assert calls[1][0] == "llm"


def test_main_removed_goal_flag_is_parser_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--goal", "stabilize core", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm should not run"))
    monkeypatch.setattr(cli, "run_code_review_full", lambda *args, **kwargs: pytest.fail("full should not run"))
    monkeypatch.setattr(cli, "run_code_review_diff", lambda *args, **kwargs: pytest.fail("diff should not run"))

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "unrecognized arguments: --goal" in captured.err
    assert "archi plan-review" not in captured.err


def test_main_full_flag_preserves_analysis_artifacts_in_output(monkeypatch, tmp_path, capsys):
    out_path = tmp_path / "legacy-full.json"
    result = _code_review_result("full")

    monkeypatch.setattr(sys, "argv", ["archi", "--full", "--out", str(out_path), str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: None)
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda path, *, checks: None)
    monkeypatch.setattr(cli, "run_code_review_full", lambda path, progress=None: result)
    monkeypatch.setattr(cli, "run_code_review_incremental_llm", lambda *args, **kwargs: pytest.fail("incremental should not run"))

    assert cli.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "code_review"
    assert payload["review_type"] == "full"
    assert payload["artifacts"]["analysis_json"] == "/tmp/.architec/architec-analysis.json"
    assert "json: /tmp/.architec/architec-analysis.json" in captured.out


def test_main_full_flag_human_summary_includes_code_review_concerns_and_signals(
    monkeypatch,
    tmp_path,
    capsys,
):
    result = _code_review_result("full")

    monkeypatch.setattr(sys, "argv", ["archi", "--full", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: None)
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda path, *, checks: None)
    monkeypatch.setattr(cli, "run_code_review_full", lambda path, progress=None: result)
    monkeypatch.setattr(cli, "run_code_review_incremental_llm", lambda *args, **kwargs: pytest.fail("incremental should not run"))

    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "Concerns: total=1 | shown=1 | limit=5" in out
    assert "Signals:" in out
    assert "- cleanup: 1 cleanup candidates; 1 marked for review." in out
    assert "Top concerns:" in out
    assert "- cleanup [caution] src/legacy.py: Cleanup candidate categorized as legacy_impl." in out
    _assert_advisory_only(out)


def test_main_bare_archi_out_json_remains_code_review_payload(monkeypatch, tmp_path, capsys):
    out_path = tmp_path / "review.json"
    result = _code_review_result("diff")

    monkeypatch.setattr(sys, "argv", ["archi", "--out", str(out_path), str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not refresh for bare archi"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda path, *, checks: None)
    monkeypatch.setattr(cli, "run_code_review_full", lambda *args, **kwargs: pytest.fail("full should not run"))
    monkeypatch.setattr(cli, "run_code_review_incremental_llm", lambda path, *, base="", head="", progress=None: result)

    assert cli.main() == 0
    capsys.readouterr()

    assert json.loads(out_path.read_text(encoding="utf-8")) == result


def test_main_legacy_full_and_diff_outputs_avoid_gate_terms(monkeypatch, tmp_path, capsys):
    full_out = tmp_path / "legacy-full.json"
    diff_out = tmp_path / "legacy-diff.json"

    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: None)
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda path, *, checks: None)
    monkeypatch.setattr(cli, "run_code_review_full", lambda path, progress=None: _code_review_result("full"))
    monkeypatch.setattr(cli, "run_code_review_diff", lambda path, *, base="", head="", progress=None: _code_review_result("diff"))
    monkeypatch.setattr(cli, "run_code_review_incremental_llm", lambda path, *, base="", head="", progress=None: _code_review_result("diff"))

    monkeypatch.setattr(sys, "argv", ["archi", "--full", "--out", str(full_out), str(tmp_path)])
    assert cli.main() == 0
    full_stdout = capsys.readouterr().out

    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "--diff", "--out", str(diff_out), str(tmp_path)],
    )
    assert cli.main() == 0
    diff_stdout = capsys.readouterr().out

    _assert_advisory_only(full_stdout + full_out.read_text(encoding="utf-8"))
    _assert_advisory_only(diff_stdout + diff_out.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("argv", "removed_name", "replacement"),
    [
        (["archi", "cleanup"], "cleanup", "archi --full"),
        (["archi", "autofix"], "autofix", "review the Archi suggestions"),
        (["archi", "baseline"], "baseline", "archi --full"),
        (["archi", "gate"], "gate", "archi"),
    ],
)
def test_main_removed_legacy_tokens_are_friendly_errors(monkeypatch, capsys, argv, removed_name, replacement):
    monkeypatch.setattr(sys, "argv", argv)
    assert not hasattr(cli, f"run_{removed_name}")
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert f"archi {removed_name} command parser has been removed" in captured.err
    assert replacement in captured.err


@pytest.mark.parametrize(
    ("argv", "replacement"),
    [
        (["archi", "cleanup", "."], "archi --full"),
        (["archi", "autofix", "--apply", "."], "review the Archi suggestions"),
        (["archi", "baseline", "--out", "baseline.json", "."], "archi --full"),
        (["archi", "gate", "--out", "gate.json", "."], "archi"),
    ],
)
def test_main_removed_legacy_commands_with_old_args_are_friendly_errors(monkeypatch, capsys, argv, replacement):
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "command parser has been removed" in captured.err
    assert replacement in captured.err


def test_emit_includes_cleanup_metadata_summary_when_present(capsys):
    cli._emit(
        {
            "summary": {
                "headline": "Architecture snapshot",
                "executive_summary": "Structure is improving.",
                "top_takeaways": [],
            },
            "scores": {"overall": 88.5},
            "cleanup": {
                "candidate_total": 2,
                "review_required_total": 2,
                "owner_total": 1,
                "ttl_total": 1,
                "expires_total": 1,
                "expired_total": 0,
                "by_category": {"stale_doc": 2},
            },
            "artifacts": {},
        },
        None,
        output_format="all",
        check_mode=False,
    )

    out = capsys.readouterr().out
    assert "Cleanup: candidates=2 | review_required=2" in out
    assert "Cleanup metadata: owner=1 | ttl=1 | expires_at=1 | expired=0" in out


def test_emit_omits_legacy_only_artifact_paths(capsys):
    cli._emit(
        {
            "summary": {"headline": "Architecture snapshot"},
            "artifacts": {
                "analysis_json": "/tmp/.architec/architec-analysis.json",
                "autofix_plan_json": "/tmp/.architec/architec-autofix-plan.json",
                "autofix_summary_md": "/tmp/.architec/architec-autofix-summary.md",
                "baseline_json": "/tmp/.architec/architec-baseline.json",
                "baseline_summary_md": "/tmp/.architec/architec-baseline-summary.md",
                "gate_json": "/tmp/.architec/architec-gate.json",
                "gate_summary_md": "/tmp/.architec/architec-gate-summary.md",
            },
        },
        None,
        output_format="all",
        check_mode=False,
    )

    out = capsys.readouterr().out
    assert "json: /tmp/.architec/architec-analysis.json" in out
    assert "autofix" not in out
    assert "baseline" not in out
    assert "gate" not in out


def test_main_status_json_still_routes_to_auth_status(monkeypatch):
    calls: list[object] = []
    monkeypatch.setattr(sys, "argv", ["archi", "status", "--json"])
    monkeypatch.setattr(cli, "handle_auth_command", lambda argv: calls.append(tuple(argv)) or 0)
    monkeypatch.setattr(cli, "run_status_trend", lambda path: pytest.fail("project status should not run"))
    monkeypatch.setattr(cli, "run_status_snapshot", lambda path: pytest.fail("project status should not run"))

    assert cli.main() == 0
    assert calls == [("status", "--json")]


def test_main_status_trend_routes_to_project_status(monkeypatch, tmp_path, capsys):
    result = {
        "mode": "status",
        "scores": {},
        "snapshot": {},
        "trend": {"event_total": 0},
        "weakening_components": [],
        "artifacts": {"review_event_jsonl": "/tmp/.architec/review-events.jsonl"},
    }
    monkeypatch.setattr(sys, "argv", ["archi", "status", "--trend", str(tmp_path)])
    monkeypatch.setattr(cli, "handle_auth_command", lambda argv: pytest.fail("auth status should not run"))
    monkeypatch.setattr(cli, "run_status_trend", lambda path: result)
    monkeypatch.setattr(cli, "run_status_snapshot", lambda path: pytest.fail("snapshot should not run"))

    assert cli.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "status"
    assert payload["trend"]["event_total"] == 0
    assert "archi status [1/1] reading advisory status trend" in captured.err


def test_main_status_snapshot_routes_to_project_status(monkeypatch, tmp_path, capsys):
    result = {
        "mode": "status",
        "scores": {"overall": 82.0},
        "snapshot": {"scores": {"overall": 82.0}},
        "trend": {"event_total": 1},
        "weakening_components": [],
        "artifacts": {"status_snapshot_json": "/tmp/.architec/status-snapshot.json"},
    }
    monkeypatch.setattr(sys, "argv", ["archi", "status", "--snapshot", str(tmp_path)])
    monkeypatch.setattr(cli, "handle_auth_command", lambda argv: pytest.fail("auth status should not run"))
    monkeypatch.setattr(cli, "run_status_trend", lambda path: pytest.fail("trend should not run"))
    monkeypatch.setattr(cli, "run_status_snapshot", lambda path: result)

    assert cli.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "status"
    assert payload["snapshot"]["scores"] == {"overall": 82.0}
    assert "archi status [1/1] writing advisory status snapshot" in captured.err


def test_main_fix_advice_outputs_json_and_skips_auth_bundle_and_llm(monkeypatch, tmp_path, capsys):
    result = {
        "mode": "fix_advice",
        "source_review": "review.json",
        "summary": {"headline": "Fix advice generated from review concerns."},
        "suggestions": [],
        "artifacts": {},
    }
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(sys, "argv", ["archi", "fix-advice", "--review", "review.json", "--focus-kind", "cleanup"])
    monkeypatch.setattr(cli, "handle_auth_command", lambda argv: pytest.fail("auth status should not run"))
    monkeypatch.setattr(cli, "inspect_bundle", lambda path: pytest.fail("bundle check should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm preflight should not run"))
    monkeypatch.setattr(
        cli,
        "run_fix_advice",
        lambda review, *, focus_file="", focus_kind="", concern_id="", advice_feedback_path=None: calls.append(
            (str(review), focus_file, focus_kind)
        )
        or result,
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "fix_advice"
    assert calls == [("review.json", "", "cleanup")]
    assert "archi fix-advice [1/1] reading review" in captured.err


def test_main_fix_advice_passes_advice_feedback_path(monkeypatch, tmp_path, capsys):
    result = {
        "mode": "fix_advice",
        "source_review": "review.json",
        "summary": {"headline": "Fix advice generated from review concerns."},
        "suggestions": [],
        "artifacts": {},
    }
    feedback = tmp_path / "feedback.json"
    feedback.write_text(json.dumps({"items": []}), encoding="utf-8")
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "fix-advice", "--review", "review.json", "--advice-feedback", str(feedback)],
    )
    monkeypatch.setattr(
        cli,
        "run_fix_advice",
        lambda review, *, focus_file="", focus_kind="", concern_id="", advice_feedback_path=None: calls.append(
            (str(review), str(advice_feedback_path))
        )
        or result,
    )

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "fix_advice"
    assert calls == [("review.json", str(feedback))]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (None, "Review JSON not found"),
        ("{not json", "Invalid review JSON"),
        ("[]", "Review JSON must be an object"),
    ],
)
def test_main_fix_advice_bad_review_input_returns_cli_error(
    monkeypatch,
    tmp_path,
    capsys,
    content,
    expected,
):
    review_path = tmp_path / "review.json"
    if content is not None:
        review_path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["archi", "fix-advice", "--for", str(review_path)])
    monkeypatch.setattr(cli, "inspect_bundle", lambda path: pytest.fail("bundle check should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm preflight should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert expected in captured.err


def test_main_plan_review_outputs_json_and_skips_auth_bundle_and_llm(monkeypatch, tmp_path, capsys):
    plan = tmp_path / "plan.md"
    plan.write_text(
        """# Plan

## Intent
Add a local advisory parser.

## Changes
```yaml
changes:
  - action: create
    path: src/architec/plan_review/public.py
    intent: parse plan markdown
dependencies: []
```
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["archi", "plan-review", "--project-root", str(tmp_path), str(plan)])
    monkeypatch.setattr(cli, "inspect_bundle", lambda path: pytest.fail("bundle check should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm preflight should not run"))

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "archi plan-review [1/1] reading plan" in captured.err
    payload = json.loads(captured.out)
    assert payload["mode"] == "plan_review"
    assert payload["understood_plan"]["changes"][0]["path"] == "src/architec/plan_review/public.py"


def test_main_plan_review_missing_file_returns_cli_error(monkeypatch, tmp_path, capsys):
    missing = tmp_path / "missing-plan.md"
    monkeypatch.setattr(sys, "argv", ["archi", "plan-review", str(missing)])

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "archi plan-review [1/1] reading plan" in captured.err
    assert "missing-plan.md" in captured.err


def test_main_code_review_full_outputs_json_contract(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = {
        "mode": "code_review",
        "review_type": "full",
        "scores": {"overall": 82.0},
        "summary": {"headline": "Project structure snapshot"},
        "findings": [],
        "signals": [{"kind": "cleanup", "candidate_total": 1}],
        "evidence": [
            {
                "kind": "cleanup",
                "location": {"path": "src/legacy/old_service.py"},
                "confidence": 0.82,
                "evidence": ["path:legacy"],
            }
        ],
        "concerns": [
            {
                "concern_id": "code-review:cleanup:1",
                "kind": "cleanup",
                "level": "caution",
                "confidence": 0.82,
                "location": {
                    "path": "src/legacy/old_service.py",
                    "line": 0,
                    "symbol": "",
                    "symbol_kind": "module",
                },
                "root_cause": "Cleanup candidate categorized as legacy_impl.",
                "evidence": ["path:legacy"],
                "blast_radius": ["src/legacy/old_service.py"],
                "next_steps_hint": "",
            }
        ],
        "artifacts": {"analysis_json": "/tmp/.architec/architec-analysis.json"},
    }

    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--full", "--allow-static", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_full",
        lambda path, progress=None: calls.append(("review", path, progress is cli.emit_progress)) or result,
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "code_review"
    assert payload["review_type"] == "full"
    assert payload["concerns"][0]["location"]["path"] == "src/legacy/old_service.py"
    assert calls[0] == ("bundle", str(tmp_path))
    assert calls[1][0] == "llm"
    assert calls[2] == ("review", str(tmp_path), True)
    encoded = json.dumps(payload, sort_keys=True).lower()
    assert "pass" not in encoded
    assert "fail" not in encoded
    assert "block" not in encoded
    assert "verdict" not in encoded
    assert "must-fix" not in encoded


def test_main_code_review_diff_outputs_json_contract(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = {
        "mode": "code_review",
        "review_type": "diff",
        "scores": {"incremental": 88.0},
        "summary": {"headline": "No new architecture concerns were identified in the selected diff."},
        "findings": [],
        "signals": [],
        "evidence": [],
        "concerns": [],
        "artifacts": {"analysis_json": "/tmp/.architec/architec-analysis.json"},
    }

    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "code-review", "--diff", "--base", "main", "--head", "HEAD", str(tmp_path)],
    )
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_diff",
        lambda path, *, base="", head="", progress=None: calls.append(
            ("review", path, base, head, progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "code_review"
    assert payload["review_type"] == "diff"
    assert payload["summary"]["headline"] == "No new architecture concerns were identified in the selected diff."
    assert payload["concerns"] == []
    assert calls[0] == ("bundle", str(tmp_path))
    assert calls[1][0] == "llm"
    assert ("architect_component_scoring", "weak") not in calls[1][2]
    assert calls[2] == ("review", str(tmp_path), "main", "HEAD", True)
    encoded = json.dumps(payload, sort_keys=True).lower()
    assert "pass" not in encoded
    assert "fail" not in encoded
    assert "block" not in encoded
    assert "verdict" not in encoded
    assert "must-fix" not in encoded


def test_main_code_review_diff_passes_plan_review_path(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = {
        "mode": "code_review",
        "review_type": "diff",
        "scores": {},
        "summary": {"headline": "No new architecture concerns were identified in the selected diff."},
        "findings": [],
        "signals": [],
        "evidence": [],
        "concerns": [],
        "artifacts": {},
    }
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "code-review", "--diff", "--plan-review", str(plan_review), str(tmp_path)],
    )
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_diff",
        lambda path, *, base="", head="", plan_review_path=None, progress=None: calls.append(
            ("review", path, base, head, str(plan_review_path), progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["review_type"] == "diff"
    assert calls[2] == ("review", str(tmp_path), "", "", str(plan_review), True)


def test_main_code_review_full_passes_risk_context_path(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = {
        "mode": "code_review",
        "review_type": "full",
        "scores": {},
        "summary": {"headline": "Full code review complete"},
        "findings": [],
        "signals": [],
        "evidence": [],
        "concerns": [],
        "artifacts": {},
    }
    risk_context = tmp_path / "risk.json"
    risk_context.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "code-review", "--full", "--risk-context", str(risk_context), str(tmp_path)],
    )
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_full",
        lambda path, *, risk_context_path=None, progress=None: calls.append(
            ("review", path, str(risk_context_path), progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["review_type"] == "full"
    assert calls[2] == ("review", str(tmp_path), str(risk_context), True)


def test_main_code_review_full_passes_advice_feedback_path(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = {
        "mode": "code_review",
        "review_type": "full",
        "scores": {},
        "summary": {"headline": "Full code review complete"},
        "findings": [],
        "signals": [],
        "evidence": [],
        "concerns": [],
        "artifacts": {},
    }
    feedback = tmp_path / "feedback.json"
    feedback.write_text(json.dumps({"items": []}), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["archi", "code-review", "--full", "--advice-feedback", str(feedback), str(tmp_path)],
    )
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_full",
        lambda path, *, advice_feedback_path=None, progress=None: calls.append(
            ("review", path, str(advice_feedback_path), progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["review_type"] == "full"
    assert calls[2] == ("review", str(tmp_path), str(feedback), True)


def test_main_code_review_full_runtime_llm_unavailable_uses_static_review(
    monkeypatch,
    tmp_path,
    capsys,
):
    calls: list[object] = []
    result = _code_review_result("full")
    result["summary"]["headline"] = "Full analysis was unavailable; static code-review signals were generated."
    result["summary"]["analysis_mode"] = "static"
    result["artifacts"] = {"code_review_analysis_mode": "static"}

    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--full", "--allow-static", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_full",
        lambda *args, **kwargs: (_ for _ in ()).throw(cli.ArchitectLLMUnavailableError("provider 403")),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_static_full",
        lambda path, *, reason="", progress=None: calls.append(
            ("static", path, reason, progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["analysis_mode"] == "static"
    assert calls[0] == ("bundle", str(tmp_path))
    assert calls[1][0] == "llm"
    assert calls[2][0] == "static"
    assert "provider 403" in calls[2][2]


def test_main_code_review_full_preflight_unavailable_is_input_error(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--full", "--allow-static", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: (_ for _ in ()).throw(cli.ArchitectLLMUnavailableError("provider 403")),
    )
    monkeypatch.setattr(cli, "run_code_review_full", lambda *args, **kwargs: pytest.fail("full should not run"))
    monkeypatch.setattr(cli, "run_code_review_static_full", lambda *args, **kwargs: pytest.fail("static should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "provider 403" in captured.err


def test_main_code_review_full_bundle_error_uses_static_review(
    monkeypatch,
    tmp_path,
    capsys,
):
    calls: list[object] = []
    result = _code_review_result("full")
    result["summary"]["headline"] = "Full analysis was unavailable; static code-review signals were generated."
    result["summary"]["analysis_mode"] = "static"
    result["artifacts"] = {"code_review_analysis_mode": "static"}

    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--full", str(tmp_path)])
    monkeypatch.setattr(
        cli,
        "_ensure_bundle",
        lambda args: (_ for _ in ()).throw(RuntimeError("refresh-from-hippo failed: file-manifest source mismatch")),
    )
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm should not run"))
    monkeypatch.setattr(cli, "run_code_review_full", lambda *args, **kwargs: pytest.fail("full should not run"))
    monkeypatch.setattr(
        cli,
        "run_code_review_static_full",
        lambda path, *, reason="", progress=None: calls.append(
            ("static", path, reason, progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["analysis_mode"] == "static"
    assert calls[0][0] == "static"
    assert "file-manifest source mismatch" in calls[0][2]
    assert "fail" not in calls[0][2].lower()


def test_main_code_review_diff_runtime_llm_unavailable_uses_static_review(
    monkeypatch,
    tmp_path,
    capsys,
):
    calls: list[object] = []
    result = _code_review_result("diff")
    result["summary"]["headline"] = "Diff analysis was unavailable; static code-review signals were generated."
    result["summary"]["analysis_mode"] = "static"
    result["artifacts"] = {"code_review_analysis_mode": "static"}

    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--diff", "--allow-static", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_diff",
        lambda *args, **kwargs: (_ for _ in ()).throw(cli.ArchitectLLMUnavailableError("provider 403")),
    )
    monkeypatch.setattr(cli, "run_code_review_static_full", lambda *args, **kwargs: pytest.fail("static should not run"))
    monkeypatch.setattr(
        cli,
        "run_code_review_static_diff",
        lambda path, *, base="", head="", reason="", progress=None: calls.append(
            ("static-diff", path, base, head, reason, progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["summary"]["analysis_mode"] == "static"
    assert calls[0][0] == "llm"
    assert calls[1][0] == "static-diff"
    assert "provider 403" in calls[1][4]


def test_main_top_level_runtime_llm_unavailable_fails_without_static_opt_in(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(sys, "argv", ["archi", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not refresh"))
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: None,
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_incremental_llm",
        lambda *args, **kwargs: (_ for _ in ()).throw(cli.ArchitectLLMUnavailableError("provider 403")),
    )
    monkeypatch.setattr(cli, "run_code_review_static_diff", lambda *args, **kwargs: pytest.fail("static should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "provider 403" in captured.err


def test_main_top_level_preflight_unavailable_is_input_error_even_with_static_opt_in(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(sys, "argv", ["archi", "--allow-static", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: pytest.fail("bundle should not refresh"))
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: (_ for _ in ()).throw(cli.ArchitectLLMUnavailableError("provider 403")),
    )
    monkeypatch.setattr(cli, "run_code_review_incremental_llm", lambda *args, **kwargs: pytest.fail("review should not run"))
    monkeypatch.setattr(cli, "run_code_review_static_diff", lambda *args, **kwargs: pytest.fail("static should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "provider 403" in captured.err


def test_main_code_review_check_llm_unavailable_remains_input_error(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(sys, "argv", ["archi", "--check", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: (_ for _ in ()).throw(cli.ArchitectLLMUnavailableError("provider 403")),
    )
    monkeypatch.setattr(cli, "run_code_review_static_full", lambda *args, **kwargs: pytest.fail("static should not run"))
    monkeypatch.setattr(cli, "run_code_review_static_diff", lambda *args, **kwargs: pytest.fail("static should not run"))

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "provider 403" in captured.err


def test_main_code_review_since_outputs_json_contract(monkeypatch, tmp_path, capsys):
    calls: list[object] = []
    result = {
        "mode": "code_review",
        "review_type": "since",
        "scores": {"incremental": 88.0},
        "summary": {"headline": "No new architecture concerns were identified in the selected since range."},
        "findings": [],
        "signals": [],
        "evidence": [],
        "concerns": [],
        "artifacts": {"analysis_json": "/tmp/.architec/architec-analysis.json"},
    }

    monkeypatch.setattr(sys, "argv", ["archi", "code-review", "--since", "main", str(tmp_path)])
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append(("bundle", args.path)) or None)
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_code_review_since",
        lambda path, *, ref="", progress=None: calls.append(
            ("review", path, ref, progress is cli.emit_progress)
        )
        or result,
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "code_review"
    assert payload["review_type"] == "since"
    assert payload["summary"]["headline"] == "No new architecture concerns were identified in the selected since range."
    assert payload["concerns"] == []
    assert calls[0] == ("bundle", str(tmp_path))
    assert calls[1][0] == "llm"
    assert ("architect_component_scoring", "weak") not in calls[1][2]
    assert calls[2] == ("review", str(tmp_path), "main", True)
    encoded = json.dumps(payload, sort_keys=True).lower()
    assert "pass" not in encoded
    assert "fail" not in encoded
    assert "block" not in encoded
    assert "verdict" not in encoded
    assert "must-fix" not in encoded


def test_emit_defaults_to_console_summary(capsys):
    cli._emit(
        {
            "summary": {
                "headline": "Architecture snapshot",
                "executive_summary": "Structure is improving.",
                "top_takeaways": ["Boundary drift remains in src root."],
            },
            "scores": {
                "overall": 88.5,
                "governance_overall": 90.0,
                "structure": 86.0,
                "full": 91.0,
                "incremental": None,
            },
            "recommendations": [
                {"priority": "P0", "title": "Split root package", "why": "Root is still too flat."}
            ],
            "artifacts": {
                "summary_md": "/tmp/.architec/architec-summary.md",
                "viz_html": "/tmp/.architec/architec-viz.html",
                "analysis_json": "/tmp/.architec/architec-analysis.json",
            },
        },
        None,
        output_format="all",
        check_mode=False,
    )

    out = capsys.readouterr().out
    assert "Architecture snapshot" in out
    assert "Scores: overall=88.5" in out
    assert "Top improvements:" in out
    assert '"summary"' not in out


def test_emit_summary_uses_chinese_locale(monkeypatch, capsys):
    monkeypatch.setenv("ARCHITEC_LANG", "zh")

    cli._emit(
        {
            "summary": {
                "headline": "",
                "executive_summary": "结构正在改善。",
                "top_takeaways": [],
            },
            "scores": {"overall": 88.5, "governance_overall": 90.0},
            "cleanup": {"candidate_total": 2, "review_required_total": 1},
            "artifacts": {"analysis_json": "/tmp/.architec/architec-analysis.json"},
        },
        None,
        output_format="all",
        check_mode=False,
    )

    out = capsys.readouterr().out
    assert "Archi 分析完成" in out
    assert "评分: 总体=88.5" in out
    assert "摘要: 结构正在改善。" in out
    assert "清理: 候选=2 | 需复核=1" in out
    assert "产物：" in out


def test_check_summary_uses_chinese_locale(monkeypatch) -> None:
    monkeypatch.setenv("ARCHITEC_LANG", "zh")

    lines = cli._summary_lines(
        {
            "checked_path": "/tmp/project",
            "checks": [{"task": "architec_summary", "tier": "strong"}],
            "refresh": {"ok": True},
        },
        check_mode=True,
    )

    assert lines == [
        "Archi 预检通过",
        "路径: /tmp/project",
        "LLM 检查: architec_summary(strong)",
        "Hippos bundle: 已刷新",
    ]


def test_emit_json_format_still_prints_summary_only(capsys):
    cli._emit(
        {
            "summary": {
                "headline": "Architecture snapshot",
            },
            "scores": {"overall": 91.0},
        },
        None,
        output_format="json",
        check_mode=False,
    )

    out = capsys.readouterr().out
    assert "Architecture snapshot" in out
    assert "Scores: overall=91.0" in out
    assert '"summary"' not in out
