from __future__ import annotations

import json

import architec.cleanup as cleanup_pkg
from architec.cleanup.autofix import (
    apply_autofix_plan,
    build_autofix_plan,
    write_autofix_artifacts,
)


def test_autofix_wrapper_export_is_retired() -> None:
    assert "run_autofix" not in cleanup_pkg.__all__
    assert not hasattr(cleanup_pkg, "run_autofix")


def test_build_autofix_plan_and_write_artifacts_preserve_metadata(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "legacy.md").write_text("Deprecated old flow\n", encoding="utf-8")

    plan = build_autofix_plan(
        cleanup={"candidate_total": 1},
        archive_candidates={"candidate_total": 1},
        semantic_judge={
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
        },
        apply=False,
    )
    artifacts = write_autofix_artifacts(tmp_path, plan=plan)

    assert plan["status"] == "planned"
    assert plan["action_total"] == 1
    plan_path = tmp_path / ".architec" / "architec-autofix-plan.json"
    summary_path = tmp_path / ".architec" / "architec-autofix-summary.md"
    assert plan_path.exists()
    assert summary_path.exists()
    assert artifacts["autofix_plan_json"] == str(plan_path)
    written_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert written_plan["actions"][0]["action"] == "archive_move"
    assert written_plan["actions"][0]["from_path"] == "docs/legacy.md"
    assert written_plan["actions"][0]["to_path"] == "archive/docs/legacy.md"
    assert written_plan["actions"][0]["owner"] == "docs-team"
    assert written_plan["actions"][0]["ttl_days"] == 14


def test_apply_autofix_plan_moves_file_to_archive(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    source = tmp_path / "docs" / "legacy.md"
    source.write_text("Deprecated old flow\n", encoding="utf-8")

    plan = build_autofix_plan(
        cleanup={"candidate_total": 1},
        archive_candidates={"candidate_total": 1},
        semantic_judge={
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
        },
        apply=True,
    )
    result = apply_autofix_plan(tmp_path, plan=plan)

    assert result["status"] == "applied"
    assert result["applied_total"] == 1
    assert result["top_actions"][0]["owner"] == "docs-team"
    assert result["top_actions"][0]["expired"] is True
    assert not source.exists()
    assert (tmp_path / "archive" / "docs" / "legacy.md").exists()
