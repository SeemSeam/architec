from __future__ import annotations

from .scope import (
    CleanupScopeEntry,
    classify_cleanup_path,
    iter_cleanup_scope,
)
from .inventory import (
    build_cleanup_inventory,
    build_cleanup_ledger,
)
from .archive import (
    archive_report_view,
    build_archive_candidates,
    render_archive_summary,
    write_archive_artifacts,
)
from .autofix import (
    apply_autofix_plan,
    autofix_report_view,
    build_autofix_plan,
    render_autofix_summary,
    run_autofix,
    write_autofix_artifacts,
)
from .semantic_judge import (
    render_semantic_judge_summary,
    run_semantic_judge,
    semantic_judge_payload,
    semantic_judge_report_view,
    write_semantic_judge_artifacts,
)
from .report import (
    cleanup_report_view,
    render_cleanup_summary,
    write_cleanup_artifacts,
)
from .public import run_cleanup
from .retire_plan import (
    build_diff_retire_plan,
    build_goal_retire_plan,
)

__all__ = [
    "CleanupScopeEntry",
    "archive_report_view",
    "apply_autofix_plan",
    "autofix_report_view",
    "build_archive_candidates",
    "build_autofix_plan",
    "build_cleanup_inventory",
    "build_cleanup_ledger",
    "build_diff_retire_plan",
    "build_goal_retire_plan",
    "classify_cleanup_path",
    "cleanup_report_view",
    "iter_cleanup_scope",
    "render_archive_summary",
    "render_autofix_summary",
    "render_cleanup_summary",
    "render_semantic_judge_summary",
    "run_cleanup",
    "run_autofix",
    "run_semantic_judge",
    "semantic_judge_payload",
    "semantic_judge_report_view",
    "write_archive_artifacts",
    "write_autofix_artifacts",
    "write_cleanup_artifacts",
    "write_semantic_judge_artifacts",
]
