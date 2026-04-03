from __future__ import annotations

import json

from architec.cleanup.autofix import run_autofix


def test_run_autofix_dry_run_writes_plan_artifacts(tmp_path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "legacy.md").write_text("Deprecated old flow\n", encoding="utf-8")
    monkeypatch.setattr(
        "architec.cleanup.autofix.run_semantic_judge",
        lambda *args, **kwargs: {
            "status": "ok",
            "reviewed_total": 1,
            "judgments": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "decision": "archive_first",
                    "confidence": 0.91,
                    "reason": "stale documentation is safe to archive",
                    "archive_path_hint": "archive/docs/legacy.md",
                    "owner": "docs-team",
                    "ttl_days": 14,
                    "expires_at": "2099-01-01",
                    "expired": False,
                }
            ],
            "top_judgments": [],
            "by_decision": {"archive_first": 1},
        },
    )

    result = run_autofix(tmp_path, apply=False, llm_enabled=True)

    assert result["meta"]["mode"] == "autofix"
    assert result["summary"]["headline"] == "Archi autofix plan ready"
    assert result["autofix"]["status"] == "planned"
    assert result["autofix"]["action_total"] == 1
    plan_path = tmp_path / ".architec" / "architec-autofix-plan.json"
    summary_path = tmp_path / ".architec" / "architec-autofix-summary.md"
    assert plan_path.exists()
    assert summary_path.exists()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["actions"][0]["action"] == "archive_move"
    assert plan["actions"][0]["from_path"] == "docs/legacy.md"
    assert plan["actions"][0]["to_path"] == "archive/docs/legacy.md"
    assert plan["actions"][0]["owner"] == "docs-team"
    assert plan["actions"][0]["ttl_days"] == 14


def test_run_autofix_apply_moves_file_to_archive(tmp_path, monkeypatch) -> None:
    (tmp_path / "docs").mkdir()
    source = tmp_path / "docs" / "legacy.md"
    source.write_text("Deprecated old flow\n", encoding="utf-8")
    monkeypatch.setattr(
        "architec.cleanup.autofix.run_semantic_judge",
        lambda *args, **kwargs: {
            "status": "ok",
            "reviewed_total": 1,
            "judgments": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "decision": "archive_first",
                    "confidence": 0.91,
                    "reason": "stale documentation is safe to archive",
                    "archive_path_hint": "archive/docs/legacy.md",
                    "owner": "docs-team",
                    "expires_at": "2000-01-01",
                    "expired": True,
                }
            ],
            "top_judgments": [],
            "by_decision": {"archive_first": 1},
        },
    )

    result = run_autofix(tmp_path, apply=True, llm_enabled=True)

    assert result["autofix"]["status"] == "applied"
    assert result["autofix"]["applied_total"] == 1
    assert result["autofix"]["top_actions"][0]["owner"] == "docs-team"
    assert result["autofix"]["top_actions"][0]["expired"] is True
    assert not source.exists()
    assert (tmp_path / "archive" / "docs" / "legacy.md").exists()
