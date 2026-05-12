from __future__ import annotations

import json

import architec.cleanup as cleanup_pkg
from architec.cleanup.archive import build_archive_candidates, write_archive_artifacts
from architec.cleanup.inventory import build_cleanup_inventory, build_cleanup_ledger
from architec.cleanup.report import cleanup_report_view, write_cleanup_artifacts
from architec.cleanup.semantic_judge import run_semantic_judge, write_semantic_judge_artifacts


def test_cleanup_wrapper_export_is_retired() -> None:
    assert "run_cleanup" not in cleanup_pkg.__all__
    assert not hasattr(cleanup_pkg, "run_cleanup")


def test_cleanup_lower_level_helpers_emit_cleanup_archive_and_semantic_artifacts(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "docs" / "legacy.md").write_text("Deprecated old flow\n", encoding="utf-8")
    (tmp_path / "config" / "legacy.toml").write_text("# temporary override\n", encoding="utf-8")
    (tmp_path / "prompts" / "legacy-review.md").write_text("Legacy prompt for migration\n", encoding="utf-8")

    inventory = build_cleanup_inventory(tmp_path)
    ledger = build_cleanup_ledger(inventory)
    cleanup = cleanup_report_view(inventory, ledger)
    archive_candidates = build_archive_candidates(inventory)
    semantic_judge = run_semantic_judge(
        tmp_path,
        cleanup_inventory=inventory,
        archive_candidates=archive_candidates,
        llm_enabled=False,
        fail_open=True,
    )
    artifacts = {
        **write_cleanup_artifacts(tmp_path, inventory=inventory, ledger=ledger),
        **write_archive_artifacts(tmp_path, archive_candidates=archive_candidates),
        **write_semantic_judge_artifacts(tmp_path, semantic_judge=semantic_judge),
    }

    assert cleanup["candidate_total"] >= 2
    assert archive_candidates["candidate_total"] >= 2
    assert semantic_judge["status"] == "skipped"
    inventory_path = tmp_path / ".architec" / "architec-cleanup-inventory.json"
    ledger_path = tmp_path / ".architec" / "architec-cleanup-ledger.json"
    summary_path = tmp_path / ".architec" / "architec-cleanup-summary.md"
    archive_path = tmp_path / ".architec" / "architec-archive-candidates.json"
    archive_summary_path = tmp_path / ".architec" / "architec-archive-summary.md"
    semantic_path = tmp_path / ".architec" / "architec-semantic-judge.json"
    semantic_summary_path = tmp_path / ".architec" / "architec-semantic-judge-summary.md"
    assert inventory_path.exists()
    assert ledger_path.exists()
    assert summary_path.exists()
    assert archive_path.exists()
    assert archive_summary_path.exists()
    assert semantic_path.exists()
    assert semantic_summary_path.exists()
    assert artifacts["cleanup_inventory_json"] == str(inventory_path)
    assert artifacts["archive_candidates_json"] == str(archive_path)
    written_inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    written_archive_candidates = json.loads(archive_path.read_text(encoding="utf-8"))
    written_semantic_judge = json.loads(semantic_path.read_text(encoding="utf-8"))
    assert written_inventory["candidate_total"] >= 2
    assert written_archive_candidates["candidate_total"] >= 2
    assert written_semantic_judge["status"] == "skipped"
