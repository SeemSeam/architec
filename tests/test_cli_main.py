from __future__ import annotations

import sys
from types import SimpleNamespace

import architec.cli as cli
import pytest
from architec.auth.guard import ArchitecAuthRequiredError


def test_build_parser_accepts_trailing_path():
    parser = cli.build_parser()
    assert parser.prog == "archi"
    args = parser.parse_args(["--goal", "review", "--diff", "--base", "main", "--head", "HEAD", "."])
    assert args.goal == "review"
    assert args.diff is True
    assert args.base == "main"
    assert args.head == "HEAD"
    assert args.path == "."


def test_build_parser_help_mentions_self_manage_commands() -> None:
    help_text = cli.build_parser().format_help()

    assert "archi update" in help_text
    assert "archi uninstall" in help_text


def test_build_cleanup_parser_accepts_trailing_path():
    parser = cli.build_cleanup_parser()
    assert parser.prog == "archi cleanup"
    args = parser.parse_args(["--out", "/tmp/cleanup.json", "."])
    assert args.out == "/tmp/cleanup.json"
    assert args.path == "."


def test_build_autofix_parser_accepts_apply_flag_and_trailing_path():
    parser = cli.build_autofix_parser()
    assert parser.prog == "archi autofix"
    args = parser.parse_args(["--out", "/tmp/autofix.json", "--apply", "."])
    assert args.out == "/tmp/autofix.json"
    assert args.apply is True
    assert args.path == "."


def test_build_baseline_parser_accepts_trailing_path():
    parser = cli.build_baseline_parser()
    assert parser.prog == "archi baseline"
    args = parser.parse_args(["--out", "/tmp/baseline.json", "--refresh-from-hippo", "."])
    assert args.out == "/tmp/baseline.json"
    assert args.refresh_from_hippo is True
    assert args.path == "."


def test_build_gate_parser_accepts_trailing_path():
    parser = cli.build_gate_parser()
    assert parser.prog == "archi gate"
    args = parser.parse_args(["--out", "/tmp/gate.json", "--refresh-from-hippo", "."])
    assert args.out == "/tmp/gate.json"
    assert args.refresh_from_hippo is True
    assert args.path == "."


def test_main_rejects_base_without_diff(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--base", "main"])
    assert cli.main() == 2
    assert "--base/--head require --diff" in capsys.readouterr().err


def test_main_version_exits_before_auth(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["archi", "--version"])
    monkeypatch.setattr(cli, "print_version_status", lambda: 0)
    monkeypatch.setattr(cli, "require_authorized_session", lambda: pytest.fail("auth should not run"))
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
    monkeypatch.setattr(cli, "require_authorized_session", lambda: {})
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda path, *, checks: None)

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "Hippo bundle missing, refreshing via hippo" in captured.err
    out = captured.out
    assert "Archi preflight OK" in out
    assert "Hippo bundle: refreshed" in out


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
    monkeypatch.setattr(cli, "require_authorized_session", lambda: {})
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda path, *, checks: None)

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "Hippo bundle stale, refreshing via hippo" in captured.err
    assert "Archi preflight OK" in captured.out


def test_main_cleanup_skips_auth_bundle_and_llm_preflight(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "cleanup", "."])
    monkeypatch.setattr(cli, "run_cleanup", lambda path, llm_enabled=False: {
        "summary": {
            "headline": "Archi cleanup complete",
            "executive_summary": "Detected 2 cleanup candidates with 2 requiring review.",
            "top_takeaways": [],
        },
        "cleanup": {
            "candidate_total": 2,
            "review_required_total": 2,
            "by_category": {"obsolete_script": 1, "stale_doc": 1},
        },
        "archive_candidates": {
            "candidate_total": 2,
            "ready_total": 1,
            "review_total": 1,
        },
        "semantic_judge": {
            "status": "ok",
            "reviewed_total": 2,
            "by_decision": {"archive_first": 1, "retire_now": 1},
        },
        "artifacts": {
            "cleanup_inventory_json": "/tmp/.architec/architec-cleanup-inventory.json",
            "cleanup_ledger_json": "/tmp/.architec/architec-cleanup-ledger.json",
            "cleanup_summary_md": "/tmp/.architec/architec-cleanup-summary.md",
            "archive_candidates_json": "/tmp/.architec/architec-archive-candidates.json",
            "archive_summary_md": "/tmp/.architec/architec-archive-summary.md",
            "semantic_judge_json": "/tmp/.architec/architec-semantic-judge.json",
            "semantic_judge_summary_md": "/tmp/.architec/architec-semantic-judge-summary.md",
        },
    })
    monkeypatch.setattr(cli, "require_authorized_session", lambda: pytest.fail("auth should not run"))
    monkeypatch.setattr(cli, "inspect_bundle", lambda path: pytest.fail("bundle check should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm preflight should not run"))

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "archi cleanup [1/1] running cleanup scan" in captured.err
    assert "Archi cleanup complete" in captured.out
    assert "Cleanup: candidates=2 | review_required=2" in captured.out
    assert "Archive: candidates=2 | ready=1 | review=1" in captured.out
    assert "Semantic judge: reviewed=2 | archive_first=1 | retire_now=1" in captured.out
    assert "cleanup inventory: /tmp/.architec/architec-cleanup-inventory.json" in captured.out
    assert "archive candidates: /tmp/.architec/architec-archive-candidates.json" in captured.out
    assert "semantic judge: /tmp/.architec/architec-semantic-judge.json" in captured.out


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


def test_main_autofix_skips_auth_bundle_and_llm_preflight(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "autofix", "."])
    monkeypatch.setattr(
        cli,
        "run_autofix",
        lambda path, apply=False, llm_enabled=True: {
            "summary": {
                "headline": "Archi autofix plan ready",
                "executive_summary": "Derived 2 safe archive-move actions.",
                "top_takeaways": [],
            },
            "cleanup": {
                "candidate_total": 2,
                "review_required_total": 2,
                "by_category": {"stale_doc": 2},
            },
            "archive_candidates": {
                "candidate_total": 2,
                "ready_total": 2,
                "review_total": 0,
            },
            "semantic_judge": {
                "status": "ok",
                "reviewed_total": 2,
                "by_decision": {"archive_first": 2},
            },
            "autofix": {
                "status": "planned",
                "action_total": 2,
                "applied_total": 0,
                "blocked_total": 0,
                "skipped_total": 0,
            },
            "artifacts": {
                "autofix_plan_json": "/tmp/.architec/architec-autofix-plan.json",
                "autofix_summary_md": "/tmp/.architec/architec-autofix-summary.md",
            },
        },
    )
    monkeypatch.setattr(cli, "require_authorized_session", lambda: pytest.fail("auth should not run"))
    monkeypatch.setattr(cli, "inspect_bundle", lambda path: pytest.fail("bundle check should not run"))
    monkeypatch.setattr(cli, "preflight_backend_llm", lambda *args, **kwargs: pytest.fail("llm preflight should not run"))

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert "archi autofix [1/1] deriving autofix actions" in captured.err
    assert "Archi autofix plan ready" in captured.out
    assert "Autofix: status=planned | actions=2 | applied=0" in captured.out
    assert "autofix plan: /tmp/.architec/architec-autofix-plan.json" in captured.out


def test_main_baseline_runs_analysis_preconditions_and_prints_baseline_artifacts(monkeypatch, capsys):
    calls: list[object] = []

    monkeypatch.setattr(sys, "argv", ["archi", "baseline", "."])
    monkeypatch.setattr(cli, "_ensure_authorized_access", lambda: calls.append("auth"))
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append("bundle") or {"ok": True})
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_baseline",
        lambda path, progress=None: {
            "summary": {
                "headline": "Archi baseline captured",
                "executive_summary": "Captured baseline at overall 82.0 with 3 cleanup candidates.",
                "top_takeaways": [],
            },
            "scores": {
                "overall": 82.0,
                "governance_overall": 79.0,
                "structure": 85.0,
                "full": 79.0,
                "incremental": None,
            },
            "cleanup": {
                "candidate_total": 3,
                "review_required_total": 3,
                "by_category": {"fallback_branch": 1, "stale_doc": 2},
            },
            "artifacts": {
                "analysis_json": "/tmp/.architec/architec-analysis.json",
                "baseline_json": "/tmp/.architec/architec-baseline.json",
                "baseline_summary_md": "/tmp/.architec/architec-baseline-summary.md",
            },
        },
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert calls[0] == "auth"
    assert calls[1] == "bundle"
    assert calls[2][0] == "llm"
    assert "Archi baseline captured" in captured.out
    assert "baseline json: /tmp/.architec/architec-baseline.json" in captured.out
    assert "baseline summary: /tmp/.architec/architec-baseline-summary.md" in captured.out


def test_main_gate_runs_analysis_preconditions_and_prints_gate_artifacts(monkeypatch, capsys):
    calls: list[object] = []

    monkeypatch.setattr(sys, "argv", ["archi", "gate", "."])
    monkeypatch.setattr(cli, "_ensure_authorized_access", lambda: calls.append("auth"))
    monkeypatch.setattr(cli, "_ensure_bundle", lambda args: calls.append("bundle") or {"ok": True})
    monkeypatch.setattr(
        cli,
        "preflight_backend_llm",
        lambda path, *, checks: calls.append(("llm", path, tuple(checks))),
    )
    monkeypatch.setattr(
        cli,
        "run_gate",
        lambda path, progress=None: {
            "summary": {
                "headline": "Archi gate passed",
                "executive_summary": "Compared current analysis against the recorded baseline and passed with 0 failing checks.",
                "top_takeaways": [],
            },
            "scores": {
                "overall": 82.0,
                "governance_overall": 79.0,
                "structure": 85.0,
                "full": 79.0,
                "incremental": None,
            },
            "cleanup": {
                "candidate_total": 3,
                "review_required_total": 3,
                "by_category": {"fallback_branch": 1, "stale_doc": 2},
            },
            "artifacts": {
                "analysis_json": "/tmp/.architec/architec-analysis.json",
                "gate_json": "/tmp/.architec/architec-gate.json",
                "gate_summary_md": "/tmp/.architec/architec-gate-summary.md",
            },
        },
    )

    assert cli.main() == 0
    captured = capsys.readouterr()
    assert calls[0] == "auth"
    assert calls[1] == "bundle"
    assert calls[2][0] == "llm"
    assert "Archi gate passed" in captured.out
    assert "gate json: /tmp/.architec/architec-gate.json" in captured.out
    assert "gate summary: /tmp/.architec/architec-gate-summary.md" in captured.out


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


def test_ensure_authorized_access_uses_existing_session(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(cli, "require_authorized_session", lambda: calls.append("require") or {})
    monkeypatch.setattr(cli, "auto_login", lambda: calls.append("login") or 0)

    cli._ensure_authorized_access()

    assert calls == ["require"]


def test_ensure_authorized_access_auto_logins_for_interactive_use(monkeypatch, capsys):
    calls: list[str] = []

    def fake_require():
        calls.append("require")
        if len(calls) == 1:
            raise ArchitecAuthRequiredError("Architec auth session is missing. Run `archi login`.")
        return {}

    monkeypatch.setattr(cli, "require_authorized_session", fake_require)
    monkeypatch.setattr(cli, "auto_login", lambda: calls.append("login") or 0)
    monkeypatch.setattr(cli, "_interactive_terminal", lambda: True)

    cli._ensure_authorized_access()

    assert calls == ["require", "login", "require"]
    err = capsys.readouterr().err
    assert "Authorizing this install in the browser..." in err


def test_ensure_authorized_access_keeps_error_for_noninteractive_use(monkeypatch):
    monkeypatch.setattr(cli, "_interactive_terminal", lambda: False)
    monkeypatch.setattr(
        cli,
        "require_authorized_session",
        lambda: (_ for _ in ()).throw(ArchitecAuthRequiredError("missing auth")),
    )

    with pytest.raises(ArchitecAuthRequiredError, match="missing auth"):
        cli._ensure_authorized_access()
