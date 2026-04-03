from __future__ import annotations

import json

from architec.cleanup.public import run_cleanup


def test_run_cleanup_emits_cleanup_artifacts_and_summary(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "docs" / "legacy.md").write_text("Deprecated old flow\n", encoding="utf-8")
    (tmp_path / "config" / "legacy.toml").write_text("# temporary override\n", encoding="utf-8")
    (tmp_path / "prompts" / "legacy-review.md").write_text("Legacy prompt for migration\n", encoding="utf-8")

    result = run_cleanup(tmp_path)

    assert result["meta"]["mode"] == "cleanup"
    assert result["summary"]["headline"] == "Archi cleanup complete"
    assert result["cleanup"]["candidate_total"] >= 2
    assert result["archive_candidates"]["candidate_total"] >= 2
    assert result["semantic_judge"]["status"] == "skipped"
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
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    archive_candidates = json.loads(archive_path.read_text(encoding="utf-8"))
    semantic_judge = json.loads(semantic_path.read_text(encoding="utf-8"))
    assert inventory["candidate_total"] >= 2
    assert archive_candidates["candidate_total"] >= 2
    assert semantic_judge["status"] == "skipped"
