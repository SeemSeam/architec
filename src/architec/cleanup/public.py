from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.cleanup.archive import (
    archive_report_view,
    build_archive_candidates,
    write_archive_artifacts,
)
from architec.cleanup.inventory import build_cleanup_inventory, build_cleanup_ledger
from architec.cleanup.report import cleanup_report_view, write_cleanup_artifacts
from architec.cleanup.semantic_judge import (
    run_semantic_judge,
    semantic_judge_report_view,
    write_semantic_judge_artifacts,
)
from architec.support.io_utils import utc_now_iso


def run_cleanup(
    project_root: str | Path,
    *,
    llm_enabled: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    inventory = build_cleanup_inventory(root)
    ledger = build_cleanup_ledger(inventory)
    cleanup = cleanup_report_view(inventory, ledger)
    archive_candidates = build_archive_candidates(inventory)
    archive = archive_report_view(archive_candidates)
    semantic_judge_result = run_semantic_judge(
        root,
        cleanup_inventory=inventory,
        archive_candidates=archive_candidates,
        llm_enabled=llm_enabled,
        fail_open=True,
    )
    semantic_judge = semantic_judge_report_view(semantic_judge_result)
    artifacts = {
        **write_cleanup_artifacts(
            root,
            inventory=inventory,
            ledger=ledger,
        ),
        **write_archive_artifacts(
            root,
            archive_candidates=archive_candidates,
        ),
        **write_semantic_judge_artifacts(
            root,
            semantic_judge=semantic_judge_result,
        ),
    }
    return {
        "meta": {
            "generated_at": utc_now_iso(),
            "path": str(root),
            "mode": "cleanup",
        },
        "summary": {
            "headline": "Archi cleanup complete",
            "executive_summary": (
                f"Detected {cleanup.get('candidate_total', 0)} cleanup candidates "
                f"with {cleanup.get('review_required_total', 0)} requiring review, "
                f"and derived {archive.get('candidate_total', 0)} archive candidates."
            ),
            "top_takeaways": [],
        },
        "cleanup": cleanup,
        "archive_candidates": archive,
        "semantic_judge": semantic_judge,
        "artifacts": artifacts,
    }


__all__ = [
    "run_cleanup",
]
