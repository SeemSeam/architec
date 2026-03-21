from __future__ import annotations

import sys
from types import SimpleNamespace

import architec.cli as cli


def test_build_parser_accepts_trailing_path():
    parser = cli.build_parser()
    assert parser.prog == "archi"
    args = parser.parse_args(["--goal", "review", "--diff", "--base", "main", "--head", "HEAD", "."])
    assert args.goal == "review"
    assert args.diff is True
    assert args.base == "main"
    assert args.head == "HEAD"
    assert args.path == "."


def test_main_rejects_base_without_diff(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--base", "main"])
    assert cli.main() == 2
    assert "--base/--head require --diff" in capsys.readouterr().err


def test_ensure_bundle_auto_refreshes_when_bundle_missing(monkeypatch):
    args = SimpleNamespace(path=".", refresh_from_hippo=False)
    calls: list[str] = []

    def fake_require_bundle(path):
        calls.append(f"require:{path}")
        raise FileNotFoundError("missing")

    def fake_refresh(path):
        calls.append(f"refresh:{path}")
        return {"ok": True, "refreshed": str(path)}

    monkeypatch.setattr(cli, "require_bundle", fake_require_bundle)
    monkeypatch.setattr(cli, "refresh_bundle_from_hippo", fake_refresh)

    result = cli._ensure_bundle(args)

    assert result == {"ok": True, "refreshed": "."}
    assert calls == ["require:.", "refresh:."]


def test_main_check_auto_refreshes_missing_bundle(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["archi", "--check", "."])

    def fake_require_bundle(path):
        raise FileNotFoundError(f"missing bundle for {path}")

    monkeypatch.setattr(cli, "require_bundle", fake_require_bundle)
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
