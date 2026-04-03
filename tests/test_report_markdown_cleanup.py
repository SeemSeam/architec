from __future__ import annotations

from architec.reporting.report_markdown import render_summary_markdown


def test_render_summary_markdown_includes_cleanup_section_without_affecting_hotspots() -> None:
    markdown = render_summary_markdown(
        {
            "meta": {"generated_at": "2026-04-02T00:00:00Z", "path": "/tmp/repo", "mode": "full", "goal": ""},
            "summary": {"executive_summary": "Stable."},
            "scores": {"overall": 90.0, "governance_overall": 91.0, "structure": 89.0, "full": 88.0, "structure_dimensions": {}},
            "hotspots": [{"path": "src/app.py", "structure_impact": "module_lines", "reason": "split module"}],
            "components": [],
            "recommendations": [],
            "cleanup": {
                "candidate_total": 2,
                "review_required_total": 2,
                "owner_total": 1,
                "ttl_total": 1,
                "expires_total": 1,
                "expired_total": 0,
                "by_category": {"stale_doc": 1, "obsolete_script": 1},
                "top_candidates": [
                    {
                        "path": "docs/legacy.md",
                        "kind": "doc",
                        "category": "stale_doc",
                        "confidence": 0.81,
                        "evidence": ["path:legacy", "content:deprecated"],
                        "owner": "docs-team",
                        "ttl_days": 14,
                        "expires_at": "2099-01-01",
                        "expired": False,
                    }
                ],
            },
            "archive_candidates": {
                "candidate_total": 2,
                "ready_total": 1,
                "review_total": 1,
                "by_category": {"stale_doc": 1, "obsolete_script": 1},
                "top_candidates": [
                    {
                        "path": "docs/legacy.md",
                        "kind": "doc",
                        "category": "stale_doc",
                        "archive_tier": "ready",
                        "archive_path_hint": "archive/docs/legacy.md",
                        "owner": "docs-team",
                    }
                ],
            },
            "semantic_judge": {
                "status": "ok",
                "candidate_pool_total": 2,
                "reviewed_total": 2,
                "by_decision": {"archive_first": 1, "retire_now": 1},
                "summary": "Reviewed top cleanup candidates and found one archive-first doc plus one retire-now source path.",
                "top_judgments": [
                    {
                        "path": "docs/legacy.md",
                        "decision": "archive_first",
                        "confidence": 0.91,
                        "reason": "stale documentation is safe to archive",
                        "archive_path_hint": "archive/docs/legacy.md",
                        "owner": "docs-team",
                    }
                ],
            },
            "feature_analysis": {
                "goal": "stabilize core",
                "retire_plan": {
                    "add": [{"component": "core", "focus_files": ["src/core/service.py"], "why": "goal_target_component"}],
                    "retire": [{"path": "src/legacy/core.py", "kind": "source", "category": "legacy_impl", "replacement": "src/core/service.py"}],
                    "validation": [{"check": "ownership", "detail": "stay inside core"}],
                },
            },
            "change_analysis": {
                "changed_file_total": 1,
                "retire_plan": {
                    "add": [{"component": "core", "focus_files": ["src/compat/core_adapter.py"], "signals": ["compat"], "why": "changed_temporary_structure"}],
                    "retire": [{"path": "docs/legacy.md", "kind": "doc", "category": "stale_doc"}],
                    "validation": [{"check": "paired_retirement", "detail": "retire old flow in same diff"}],
                },
            },
        }
    )

    assert "## Top Hotspots" in markdown
    assert "`src/app.py` | impact=`module_lines`" in markdown
    assert "## Cleanup Candidates" in markdown
    assert "`docs/legacy.md` [doc] -> `stale_doc`" in markdown
    assert "owner=`1` | ttl=`1` | expires_at=`1` | expired=`0`" in markdown
    assert "owner=docs-team" in markdown
    assert "## Archive Candidates" in markdown
    assert "tier=`ready`" in markdown
    assert "## Semantic Judge" in markdown
    assert "`docs/legacy.md` -> `archive_first`" in markdown
    assert "## Goal Retire Plan" in markdown
    assert "Add `core` | focus: src/core/service.py" in markdown
    assert "## Diff Retire Plan" in markdown
    assert "Retire `docs/legacy.md` [doc] -> `stale_doc`" in markdown
