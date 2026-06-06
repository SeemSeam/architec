from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import architec.code_review.public as code_review
import pytest


def _analysis_report() -> dict[str, object]:
    return {
        "scores": {
            "overall": 82.0,
            "structure": 79.5,
            "full": 76.0,
            "incremental": None,
        },
        "summary": {
            "headline": "Project structure snapshot",
            "executive_summary": "Cleanup candidates are concentrated in legacy files.",
            "top_takeaways": [],
        },
        "recommendations": [
            {"priority": "P0", "title": "Clarify legacy ownership", "why": "Ownership is unclear."}
        ],
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "owner_total": 1,
            "ttl_total": 1,
            "expires_total": 1,
            "expired_total": 0,
            "by_category": {"legacy_impl": 1},
            "top_candidates": [
                {
                    "path": "src/legacy/old_service.py",
                    "kind": "source",
                    "category": "legacy_impl",
                    "confidence": 0.82,
                    "evidence": ["path:legacy", "content:deprecated"],
                }
            ],
        },
        "archive_candidates": {
            "candidate_total": 1,
            "ready_total": 1,
            "review_total": 0,
            "by_tier": {"ready": 1},
            "by_category": {"stale_doc": 1},
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.74,
                    "review_required": False,
                    "archive_tier": "ready",
                    "archive_path_hint": "archive/docs/legacy.md",
                }
            ],
        },
        "semantic_judge": {
            "status": "ok",
            "reviewed_total": 1,
            "candidate_pool_total": 2,
            "by_decision": {"archive_first": 1},
        },
        "hotspots": [{"path": "src/legacy/old_service.py"}],
        "topology": {
            "needs_folder_management": True,
            "flat_file_total": 12,
        },
        "artifacts": {
            "analysis_json": "/tmp/.architec/architec-analysis.json",
        },
    }


def _empty_review_report() -> dict[str, object]:
    return {
        "scores": {},
        "summary": {},
        "cleanup": {},
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [],
        "topology": {},
        "artifacts": {},
    }


def _global_context_report(changed_files: list[str]) -> dict[str, object]:
    report = copy.deepcopy(_analysis_report())
    report["change_analysis"] = {
        "changed_file_total": len(changed_files),
        "changed_files": changed_files,
        "components": [],
    }
    report["topology"] = {
        "needs_folder_management": True,
        "flat_file_total": 12,
        "confidence": 0.71,
        "root_placement_review": {
            "review_root_files": [{"path": "src/global/topology.py"}],
        },
    }
    return report


def _write_near_duplicate_project(tmp_path) -> None:
    source = tmp_path / "src"
    source.mkdir(exist_ok=True)
    (source / "existing.py").write_text(
        """
def existing_impl(value):
    total = 0
    for item in value:
        if item > 10:
            total += item * 2
        else:
            total += item
    return total
""",
        encoding="utf-8",
    )
    (source / "changed.py").write_text(
        """
def changed_impl(records):
    result = 0
    for row in records:
        if row > 99:
            result += row * 2
        else:
            result += row
    return result
""",
        encoding="utf-8",
    )


def test_run_code_review_full_reuses_full_analysis_and_maps_cleanup_concern(tmp_path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_analysis(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return _analysis_report()

    monkeypatch.setattr(code_review, "run_analysis", fake_run_analysis)

    result = code_review.run_code_review_full(tmp_path)

    assert calls == [
        {
            "args": (tmp_path,),
            "kwargs": {"goal": "", "diff": False, "base": "", "head": "", "progress": None},
        }
    ]
    assert result["mode"] == "code_review"
    assert result["review_type"] == "full"
    assert set(result) == {
        "mode",
        "review_type",
        "scores",
        "summary",
        "findings",
        "signals",
        "evidence",
        "concerns",
        "artifacts",
    }
    concern = next(item for item in result["concerns"] if item["kind"] == "cleanup")
    assert concern["kind"] == "cleanup"
    assert concern["location"]["path"] == "src/legacy/old_service.py"
    assert concern["location"]["line"] == 0
    evidence = next(item for item in result["evidence"] if item["concern_id"] == concern["concern_id"])
    assert evidence["evidence_id"] == "code-review:evidence:1"
    assert evidence["location"]["path"] == "src/legacy/old_service.py"
    assert evidence["facts"] == concern["evidence"]
    event_path = tmp_path / ".architec" / "review-events.jsonl"
    assert result["artifacts"]["review_event_jsonl"] == str(event_path)
    assert json.loads(event_path.read_text(encoding="utf-8"))["mode"] == "code_review"


def test_run_code_review_event_write_failure_is_reported_in_artifacts(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    def raise_os_error(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(code_review, "append_review_event", raise_os_error)

    result = code_review.run_code_review_full(tmp_path)

    assert result["mode"] == "code_review"
    assert result["artifacts"]["review_event_error"] == "disk full"
    assert "review_event_jsonl" not in result["artifacts"]


def test_run_code_review_event_write_non_os_error_is_not_swallowed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    def raise_bug(*args, **kwargs):
        raise ValueError("event builder bug")

    monkeypatch.setattr(code_review, "append_review_event", raise_bug)

    with pytest.raises(ValueError, match="event builder bug"):
        code_review.run_code_review_full(tmp_path)


def test_run_code_review_diff_reuses_diff_analysis_args(tmp_path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_analysis(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return _analysis_report()

    monkeypatch.setattr(code_review, "run_analysis", fake_run_analysis)

    result = code_review.run_code_review_diff(tmp_path, base="main", head="HEAD")

    assert calls == [
        {
            "args": (tmp_path,),
            "kwargs": {"goal": "", "diff": True, "base": "main", "head": "HEAD", "progress": None},
        }
    ]
    assert result["mode"] == "code_review"
    assert result["review_type"] == "diff"
    assert set(result) == {
        "mode",
        "review_type",
        "scores",
        "summary",
        "findings",
        "signals",
        "evidence",
        "concerns",
        "artifacts",
    }


def test_run_code_review_diff_empty_concerns_uses_fixed_summary(tmp_path, monkeypatch) -> None:
    report = {
        "scores": {"overall": 91.0, "incremental": 88.0},
        "cleanup": {
            "candidate_total": 0,
            "review_required_total": 0,
            "top_candidates": [],
        },
        "hotspots": [],
        "topology": {},
        "artifacts": {},
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    assert result["review_type"] == "diff"
    assert result["summary"]["headline"] == "No new architecture concerns were identified in the selected diff."
    assert result["summary"]["concern_total"] == 0
    assert result["summary"]["top_concern_total"] == 0
    assert result["summary"]["concern_limit"] == 5
    assert result["concerns"] == []
    assert result["findings"] == []
    encoded = json.dumps({"headline": result["summary"]["headline"]}, sort_keys=True).lower()
    for term in ("pass", "fail", "block", "verdict", "must-fix", "clean", "safe"):
        assert term not in encoded


def test_code_review_diff_hides_unrelated_global_context_from_top_concerns(
    tmp_path,
    monkeypatch,
) -> None:
    report = _global_context_report(["tests/test_llm_transport.py", "opencode.json"])
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    assert result["concerns"] == []
    assert result["evidence"] == []
    assert result["summary"]["concern_total"] == 4
    assert result["summary"]["top_concern_total"] == 0
    assert result["summary"]["scoped_concern_total"] == 0
    assert result["summary"]["global_context_concern_total"] == 4
    assert result["summary"]["displayed_scoped_concern_total"] == 0
    assert result["summary"]["displayed_global_context_concern_total"] == 0
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert artifact["concern_total"] == 4
    assert len(artifact["concerns"]) == 4
    assert {item["location"]["path"] for item in artifact["concerns"]} == {
        "src/legacy/old_service.py",
        "docs/legacy.md",
        "src/global/topology.py",
    }


def test_code_review_since_hides_unrelated_global_context_from_top_concerns(
    tmp_path,
    monkeypatch,
) -> None:
    report = _global_context_report(["tests/test_prompt_propagation.py"])
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_since(tmp_path, ref="main")

    assert result["concerns"] == []
    assert result["evidence"] == []
    assert result["summary"]["concern_total"] == 4
    assert result["summary"]["top_concern_total"] == 0
    assert result["summary"]["scoped_concern_total"] == 0
    assert result["summary"]["global_context_concern_total"] == 4


def test_code_review_diff_displays_global_context_when_own_file_changed(
    tmp_path,
    monkeypatch,
) -> None:
    report = _global_context_report(["src/legacy/old_service.py"])
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    assert {item["location"]["path"] for item in result["concerns"]} == {
        "src/legacy/old_service.py",
    }
    assert {item["kind"] for item in result["concerns"]} == {"cleanup", "hotspot"}
    assert result["summary"]["concern_total"] == 4
    assert result["summary"]["scoped_concern_total"] == 2
    assert result["summary"]["global_context_concern_total"] == 2
    assert result["summary"]["top_concern_total"] == 2
    assert result["summary"]["displayed_scoped_concern_total"] == 2
    assert result["summary"]["displayed_global_context_concern_total"] == 0


def test_run_code_review_since_reuses_diff_analysis_args(tmp_path, monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run_analysis(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return _analysis_report()

    monkeypatch.setattr(code_review, "run_analysis", fake_run_analysis)

    result = code_review.run_code_review_since(tmp_path, ref="main")

    assert calls == [
        {
            "args": (tmp_path,),
            "kwargs": {"goal": "", "diff": True, "base": "main", "head": "HEAD", "progress": None},
        }
    ]
    assert result["mode"] == "code_review"
    assert result["review_type"] == "since"
    assert set(result) == {
        "mode",
        "review_type",
        "scores",
        "summary",
        "findings",
        "signals",
        "evidence",
        "concerns",
        "artifacts",
    }


def test_run_code_review_since_empty_concerns_uses_fixed_summary(tmp_path, monkeypatch) -> None:
    report = {
        "scores": {"overall": 91.0, "incremental": 88.0},
        "cleanup": {
            "candidate_total": 0,
            "review_required_total": 0,
            "top_candidates": [],
        },
        "hotspots": [],
        "topology": {},
        "artifacts": {},
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_since(tmp_path, ref="main")

    assert result["review_type"] == "since"
    assert result["summary"]["headline"] == "No new architecture concerns were identified in the selected since range."
    assert result["summary"]["concern_total"] == 0
    assert result["summary"]["top_concern_total"] == 0
    assert result["summary"]["concern_limit"] == 5
    assert result["concerns"] == []
    assert result["findings"] == []
    encoded = json.dumps({"headline": result["summary"]["headline"]}, sort_keys=True).lower()
    for term in ("pass", "fail", "block", "verdict", "must-fix", "clean", "safe"):
        assert term not in encoded


def test_run_code_review_since_unresolved_ref_degrades_to_result(tmp_path, monkeypatch) -> None:
    def raise_bad_ref(*args, **kwargs):
        raise RuntimeError("fatal: bad revision 'missing-ref...HEAD'")

    monkeypatch.setattr(code_review, "run_analysis", raise_bad_ref)

    result = code_review.run_code_review_since(tmp_path, ref="missing-ref")

    assert result["mode"] == "code_review"
    assert result["review_type"] == "since"
    assert result["summary"]["headline"] == "Unable to analyze the requested since range."
    assert result["summary"]["reason"] == "The requested since range could not be resolved."
    assert result["summary"]["concern_total"] == 0
    assert result["summary"]["top_concern_total"] == 0
    assert result["summary"]["concern_limit"] == 5
    assert result["concerns"] == []
    assert result["findings"] == []
    assert result["artifacts"] == {}
    encoded = json.dumps(
        {
            "headline": result["summary"]["headline"],
            "reason": result["summary"]["reason"],
        },
        sort_keys=True,
    ).lower()
    for term in ("pass", "fail", "block", "verdict", "must-fix", "clean", "safe"):
        assert term not in encoded


def test_run_code_review_since_git_range_error_degrades_to_result(tmp_path, monkeypatch) -> None:
    def raise_git_range_error(*args, **kwargs):
        raise RuntimeError("git range error while running `git diff --numstat missing...HEAD`: fatal: bad revision")

    monkeypatch.setattr(code_review, "run_analysis", raise_git_range_error)

    result = code_review.run_code_review_since(tmp_path, ref="missing")

    assert result["mode"] == "code_review"
    assert result["review_type"] == "since"
    assert result["summary"]["headline"] == "Unable to analyze the requested since range."
    assert result["summary"]["reason"] == "The requested since range could not be resolved."
    assert result["concerns"] == []
    assert result["findings"] == []
    assert result["artifacts"] == {}


def test_run_code_review_since_unrelated_runtime_error_is_not_swallowed(tmp_path, monkeypatch) -> None:
    def raise_bug(*args, **kwargs):
        raise RuntimeError("cleanup mapper exploded")

    monkeypatch.setattr(code_review, "run_analysis", raise_bug)

    with pytest.raises(RuntimeError, match="cleanup mapper exploded"):
        code_review.run_code_review_since(tmp_path, ref="main")


def test_run_code_review_full_maps_hotspot_file_concern(tmp_path, monkeypatch) -> None:
    report = {
        **_analysis_report(),
        "cleanup": {},
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [
            {
                "path": "src/core/large_service.py",
                "rank": 1,
                "component": "core",
                "structure_impact": "module_lines",
                "confidence": 0.91,
            }
        ],
        "topology": {},
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    concern = result["concerns"][0]
    assert concern["kind"] == "hotspot"
    assert concern["location"]["path"] == "src/core/large_service.py"
    assert concern["location"]["line"] == 0
    assert "hotspot.metric=module_lines" in concern["evidence"]


def test_run_code_review_full_maps_topology_file_boundary_concern(tmp_path, monkeypatch) -> None:
    report = {
        **_analysis_report(),
        "cleanup": {},
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [],
        "topology": {
            "source_root": "src/architec",
            "needs_folder_management": True,
            "flat_file_total": 12,
            "confidence": 0.73,
            "root_placement_review": {
                "misplaced_root_files": [{"path": "src/architec/io_utils.py"}],
            },
            "migration_plan": {
                "file_moves": [{"from": "src/architec/report.py", "to": "src/architec/reporting/report.py"}],
                "review_files": [{"path": "src/architec/paths.py"}],
            },
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    concern = next(
        item
        for item in result["concerns"]
        if item["location"]["path"] == "src/architec/io_utils.py"
    )
    assert concern["kind"] == "boundary"
    assert concern["location"]["path"] == "src/architec/io_utils.py"
    assert "topology.root_placement=misplaced_root_files" in concern["evidence"]


def test_run_code_review_full_maps_archive_signal_and_file_concern(tmp_path, monkeypatch) -> None:
    report = {
        **_analysis_report(),
        "cleanup": {},
        "hotspots": [],
        "topology": {},
        "archive_candidates": {
            "candidate_total": 2,
            "ready_total": 1,
            "review_total": 1,
            "by_tier": {"ready": 1, "review": 1},
            "by_category": {"stale_config": 1, "stale_doc": 1},
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.88,
                    "review_required": False,
                    "archive_tier": "ready",
                    "archive_path_hint": "archive/docs/legacy.md",
                }
            ],
        },
        "semantic_judge": {},
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    concern = result["concerns"][0]
    assert concern["kind"] == "cleanup"
    assert concern["location"]["path"] == "docs/legacy.md"
    assert "archive.category=stale_doc" in concern["evidence"]
    assert "archive.tier=ready" in concern["evidence"]
    assert "archive.path_hint=archive/docs/legacy.md" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "archive")
    assert signal["metrics"] == {
        "candidate_total": 2,
        "ready_total": 1,
        "review_total": 1,
        "by_tier": {"ready": 1, "review": 1},
        "by_category": {"stale_config": 1, "stale_doc": 1},
    }


def test_run_code_review_full_demotes_active_changelog_stale_doc_from_display(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / "CHANGELOG.md").write_text(
        """
# Changelog

## Unreleased

- Continue tracking current user-facing changes.
""",
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [
                {
                    "path": "CHANGELOG.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.95,
                    "evidence": ["content:historical versions"],
                }
            ],
        },
        "archive_candidates": {
            "candidate_total": 1,
            "ready_total": 1,
            "review_total": 0,
            "by_tier": {"ready": 1},
            "by_category": {"stale_doc": 1},
            "top_candidates": [
                {
                    "path": "CHANGELOG.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.9,
                    "review_required": False,
                    "archive_tier": "ready",
                }
            ],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["concern_total"] == 2
    assert result["summary"]["top_concern_total"] == 0
    assert result["concerns"] == []
    assert {"cleanup", "archive"}.issubset(set(result["summary"]["signal_kinds"]))
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert artifact["concern_total"] == 2
    assert [item["location"]["path"] for item in artifact["concerns"]] == [
        "CHANGELOG.md",
        "CHANGELOG.md",
    ]


def test_run_code_review_full_dedupes_cleanup_archive_same_path_category_display(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.70,
                }
            ],
        },
        "archive_candidates": {
            "candidate_total": 1,
            "ready_total": 1,
            "review_total": 0,
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.95,
                    "archive_tier": "ready",
                }
            ],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["concern_total"] == 2
    assert result["summary"]["top_concern_total"] == 1
    assert [item["location"]["path"] for item in result["concerns"]] == ["docs/legacy.md"]
    assert "archive.category=stale_doc" in result["concerns"][0]["evidence"]
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert artifact["concern_total"] == 2
    assert len(artifact["concerns"]) == 2


def test_code_review_diff_dedupes_scoped_cleanup_archive_same_path_category_display(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["docs/legacy.md"],
            "components": [],
        },
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.70,
                }
            ],
        },
        "archive_candidates": {
            "candidate_total": 1,
            "ready_total": 1,
            "review_total": 0,
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.95,
                    "archive_tier": "ready",
                }
            ],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    assert result["summary"]["concern_total"] == 2
    assert result["summary"]["scoped_concern_total"] == 2
    assert result["summary"]["global_context_concern_total"] == 0
    assert result["summary"]["displayed_scoped_concern_total"] == 1
    assert result["summary"]["displayed_global_context_concern_total"] == 0
    assert result["summary"]["top_concern_total"] == 1
    assert [item["location"]["path"] for item in result["concerns"]] == ["docs/legacy.md"]
    assert "archive.category=stale_doc" in result["concerns"][0]["evidence"]
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert artifact["concern_total"] == 2
    assert len(artifact["concerns"]) == 2


def test_run_code_review_full_demotes_semantic_keep_active_stale_doc_from_display(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [
                {
                    "path": "docs/Makefile",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.73,
                    "evidence": ["content:deprecated"],
                }
            ],
        },
        "archive_candidates": {
            "candidate_total": 1,
            "ready_total": 1,
            "review_total": 0,
            "top_candidates": [
                {
                    "path": "docs/Makefile",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.91,
                    "review_required": True,
                    "archive_tier": "ready",
                }
            ],
        },
        "semantic_judge": {
            "status": "ok",
            "candidate_pool_total": 1,
            "reviewed_total": 1,
            "by_decision": {"keep_active": 1},
            "top_judgments": [
                {
                    "path": "docs/Makefile",
                    "kind": "doc",
                    "category": "stale_doc",
                    "decision": "keep_active",
                }
            ],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["concern_total"] == 2
    assert result["summary"]["top_concern_total"] == 0
    assert result["concerns"] == []
    assert {"cleanup", "archive", "semantic_judge"}.issubset(set(result["summary"]["signal_kinds"]))
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert artifact["concern_total"] == 2
    assert [item["location"]["path"] for item in artifact["concerns"]] == [
        "docs/Makefile",
        "docs/Makefile",
    ]


def test_run_code_review_full_keeps_stale_doc_when_semantic_judge_requests_review(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.73,
                }
            ],
        },
        "semantic_judge": {
            "status": "ok",
            "candidate_pool_total": 1,
            "reviewed_total": 1,
            "by_decision": {"review": 1},
            "judgments": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "decision": "review",
                }
            ],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["concern_total"] == 1
    assert result["summary"]["top_concern_total"] == 1
    assert result["concerns"][0]["location"]["path"] == "docs/legacy.md"
    assert result["concerns"][0]["confidence"] == 0.76
    assert "semantic_judge.decision=review" in result["concerns"][0]["evidence"]
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert artifact["concerns"][0]["confidence"] == 0.76
    assert "semantic_judge.decision=review" in artifact["concerns"][0]["evidence"]


def test_run_code_review_full_reinforces_cleanup_archive_first_semantic_decision(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [
                {
                    "path": "src/legacy/old_service.py",
                    "kind": "source",
                    "category": "legacy_impl",
                    "confidence": 0.52,
                }
            ],
        },
        "semantic_judge": {
            "status": "ok",
            "candidate_pool_total": 1,
            "reviewed_total": 1,
            "by_decision": {"archive_first": 1},
            "top_judgments": [
                {
                    "path": "src/legacy/old_service.py",
                    "kind": "source",
                    "category": "legacy_impl",
                    "decision": "archive_first",
                }
            ],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    concern = result["concerns"][0]
    assert concern["kind"] == "cleanup"
    assert concern["confidence"] == 0.8
    assert "cleanup.category=legacy_impl" in concern["evidence"]
    assert "semantic_judge.decision=archive_first" in concern["evidence"]
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert "semantic_judge.decision=archive_first" in artifact["concerns"][0]["evidence"]


def test_run_code_review_full_reinforces_archive_retire_now_semantic_decision(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "archive_candidates": {
            "candidate_total": 1,
            "ready_total": 1,
            "review_total": 0,
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.58,
                    "review_required": False,
                    "archive_tier": "ready",
                }
            ],
        },
        "semantic_judge": {
            "status": "ok",
            "candidate_pool_total": 1,
            "reviewed_total": 1,
            "by_decision": {"retire_now": 1},
            "judgments": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "decision": "retire_now",
                }
            ],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    concern = result["concerns"][0]
    assert concern["kind"] == "cleanup"
    assert concern["confidence"] >= 0.86
    assert "archive.category=stale_doc" in concern["evidence"]
    assert "semantic_judge.decision=retire_now" in concern["evidence"]


def test_run_code_review_full_ignores_archive_retire_semantic_decision_when_status_not_ok(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [
                {
                    "path": "src/legacy/old_service.py",
                    "kind": "source",
                    "category": "legacy_impl",
                    "confidence": 0.52,
                }
            ],
        },
        "semantic_judge": {
            "status": "skipped",
            "candidate_pool_total": 1,
            "reviewed_total": 0,
            "by_decision": {"archive_first": 1},
            "top_judgments": [
                {
                    "path": "src/legacy/old_service.py",
                    "decision": "archive_first",
                }
            ],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    concern = result["concerns"][0]
    assert concern["confidence"] == 0.52
    assert "semantic_judge.decision=archive_first" not in concern["evidence"]


def test_run_code_review_full_does_not_boost_non_cleanup_semantic_archive_first(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "hotspots": [{"path": "src/core.py", "confidence": 0.4}],
        "semantic_judge": {
            "status": "ok",
            "candidate_pool_total": 1,
            "reviewed_total": 1,
            "by_decision": {"archive_first": 1},
            "judgments": [{"path": "src/core.py", "decision": "archive_first"}],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert result["concerns"][0]["kind"] == "hotspot"
    assert result["concerns"][0]["confidence"] == 0.4
    assert "semantic_judge.decision=archive_first" not in result["concerns"][0]["evidence"]


def test_run_code_review_full_does_not_boost_non_cleanup_semantic_review(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "hotspots": [{"path": "src/core.py", "confidence": 0.4}],
        "semantic_judge": {
            "status": "ok",
            "candidate_pool_total": 1,
            "reviewed_total": 1,
            "by_decision": {"review": 1},
            "judgments": [{"path": "src/core.py", "decision": "review"}],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert result["concerns"][0]["kind"] == "hotspot"
    assert result["concerns"][0]["confidence"] == 0.4
    assert "semantic_judge.decision=review" not in result["concerns"][0]["evidence"]


def test_run_code_review_full_semantic_archive_retire_output_avoids_forbidden_terms(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [
                {
                    "path": "src/legacy/old_service.py",
                    "kind": "source",
                    "category": "legacy_impl",
                    "confidence": 0.52,
                }
            ],
        },
        "semantic_judge": {
            "status": "ok",
            "candidate_pool_total": 1,
            "reviewed_total": 1,
            "by_decision": {"retire_now": 1},
            "judgments": [{"path": "src/legacy/old_service.py", "decision": "retire_now"}],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)
    payload = json.dumps(result, sort_keys=True)

    forbidden = ("pass", "fail", "block", "verdict", "must-fix", "patch", "apply")
    assert all(term not in payload.lower() for term in forbidden)


def test_run_code_review_full_demotes_small_flat_topology_boundary_from_display(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "topology": {
            "source_root": "src/package",
            "needs_folder_management": False,
            "flat_file_total": 4,
            "confidence": 0.92,
            "root_placement_review": {
                "review_root_files": [{"path": "src/package/helpers.py"}],
            },
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["concern_total"] == 1
    assert result["summary"]["top_concern_total"] == 0
    assert result["concerns"] == []
    topology = next(signal for signal in result["signals"] if signal["kind"] == "topology")
    assert topology["metrics"] == {"needs_folder_management": False, "flat_file_total": 4}
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert artifact["concern_total"] == 1
    assert artifact["concerns"][0]["location"]["path"] == "src/package/helpers.py"


def test_run_code_review_full_displays_larger_flat_topology_boundary(
    tmp_path,
    monkeypatch,
) -> None:
    report = {
        **_empty_review_report(),
        "topology": {
            "source_root": "src/package",
            "needs_folder_management": False,
            "flat_file_total": 11,
            "confidence": 0.92,
            "root_placement_review": {
                "review_root_files": [{"path": "src/package/helpers.py"}],
            },
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["concern_total"] == 1
    assert result["summary"]["top_concern_total"] == 1
    assert result["concerns"][0]["kind"] == "boundary"
    assert result["concerns"][0]["location"]["path"] == "src/package/helpers.py"


def test_run_code_review_full_limits_ranked_concerns_to_top_five(tmp_path, monkeypatch) -> None:
    report = {
        **_analysis_report(),
        "cleanup": {
            "candidate_total": 2,
            "review_required_total": 2,
            "top_candidates": [
                {"path": "src/a.py", "category": "legacy", "confidence": 0.99},
                {"path": "src/b.py", "category": "legacy", "confidence": 0.98},
            ],
        },
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [
            {"path": "src/c.py", "confidence": 0.97},
            {"path": "src/d.py", "confidence": 0.96},
            {"path": "src/e.py", "confidence": 0.95},
            {"path": "src/f.py", "confidence": 0.2},
        ],
        "topology": {
            "needs_folder_management": True,
            "flat_file_total": 3,
            "confidence": 0.94,
            "root_placement_review": {
                "review_root_files": [{"path": "src/g.py"}],
            },
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    assert len(result["concerns"]) == 5
    assert result["summary"]["concern_total"] == 7
    assert result["summary"]["top_concern_total"] == 5
    assert result["summary"]["concern_limit"] == 5
    paths = [item["location"]["path"] for item in result["concerns"]]
    assert paths == ["src/a.py", "src/b.py", "src/c.py", "src/d.py", "src/g.py"]
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    assert result["artifacts"]["code_review_concerns_json"] == str(
        tmp_path / ".architec" / "code-review-concerns.json"
    )
    assert artifact["mode"] == "code_review"
    assert artifact["review_type"] == "full"
    assert artifact["concern_total"] == 7
    assert artifact["top_concern_total"] == 5
    assert len(artifact["concerns"]) == 7


def _ranking_concern(kind: str, path: str, confidence: float, *, level: str = "caution") -> dict[str, object]:
    return {
        "concern_id": f"code-review:{kind}:{path}",
        "kind": kind,
        "level": level,
        "confidence": confidence,
        "location": {"path": path, "line": 0, "symbol": "", "symbol_kind": "module"},
        "root_cause": "test concern",
        "evidence": [f"test.path={path}"],
    }


def test_ranked_concerns_diversifies_kind_within_same_level() -> None:
    ranked = code_review._ranked_concerns(
        [
            _ranking_concern("duplication", "src/dup1.py", 0.99),
            _ranking_concern("duplication", "src/dup2.py", 0.98),
            _ranking_concern("duplication", "src/dup3.py", 0.97),
            _ranking_concern("duplication", "src/dup4.py", 0.96),
            _ranking_concern("boundary", "src/boundary.py", 0.50),
            _ranking_concern("hotspot", "src/hotspot.py", 0.40),
            _ranking_concern("cleanup", "src/cleanup.py", 0.30),
        ],
        limit=5,
    )

    kinds = [str(item["kind"]) for item in ranked]
    assert len(ranked) == 5
    assert kinds.count("duplication") == 2
    assert {"boundary", "hotspot", "cleanup"}.issubset(kinds)


def test_ranked_concerns_does_not_promote_lower_level_for_diversity() -> None:
    ranked = code_review._ranked_concerns(
        [
            _ranking_concern("duplication", f"src/high{i}.py", 0.99 - i * 0.01, level="high-concern")
            for i in range(5)
        ]
        + [
            _ranking_concern("boundary", "src/boundary.py", 0.99, level="caution"),
            _ranking_concern("hotspot", "src/hotspot.py", 0.98, level="caution"),
        ],
        limit=5,
    )

    assert len(ranked) == 5
    assert {str(item["level"]) for item in ranked} == {"high-concern"}
    assert [str(item["kind"]) for item in ranked] == ["duplication"] * 5


def test_ranked_concerns_single_kind_still_fills_limit() -> None:
    ranked = code_review._ranked_concerns(
        [
            _ranking_concern("duplication", f"src/dup{i}.py", 0.99 - i * 0.01)
            for i in range(7)
        ],
        limit=5,
    )

    assert len(ranked) == 5
    assert [str(item["kind"]) for item in ranked] == ["duplication"] * 5


def test_ranked_concerns_order_is_deterministic() -> None:
    concerns = [
        _ranking_concern("duplication", "src/dup1.py", 0.99),
        _ranking_concern("duplication", "src/dup2.py", 0.98),
        _ranking_concern("duplication", "src/dup3.py", 0.97),
        _ranking_concern("boundary", "src/boundary.py", 0.50),
        _ranking_concern("hotspot", "src/hotspot.py", 0.40),
        _ranking_concern("cleanup", "src/cleanup.py", 0.30),
    ]

    first = code_review._ranked_concerns(concerns, limit=5)
    second = code_review._ranked_concerns(list(reversed(concerns)), limit=5)

    assert [item["concern_id"] for item in first] == [item["concern_id"] for item in second]


def test_code_review_payload_guard_truncates_large_concern_fields() -> None:
    concern_id = "code-review:duplication:stable"
    result = {
        "mode": "code_review",
        "review_type": "full",
        "scores": {},
        "summary": {
            "headline": "Full code review complete",
            "concern_total": 1,
            "top_concern_total": 1,
            "concern_limit": 5,
            "signal_kinds": ["near_duplicate"],
        },
        "findings": [],
        "signals": [
            {
                "kind": "near_duplicate",
                "summary": "many duplicates",
                "metrics": {"by_path": {f"src/{index:02d}.py": index for index in range(20)}},
            }
        ],
        "evidence": [],
        "concerns": [
            {
                "concern_id": concern_id,
                "kind": "duplication",
                "level": "caution",
                "confidence": 0.9,
                "location": {"path": "src/changed.py", "line": 2, "symbol": "changed"},
                "root_cause": "test",
                "evidence": [f"fact={index}" for index in range(20)],
                "references": [
                    {"role": "reference", "path": f"src/ref{index}.py", "line": index}
                    for index in range(5)
                ],
                "blast_radius": [f"src/blast{index}.py" for index in range(12)],
            }
        ],
        "artifacts": {},
    }

    finalized = code_review._finalize_payload(copy.deepcopy(result))

    concern = finalized["concerns"][0]
    assert concern["concern_id"] == concern_id
    assert len(concern["evidence"]) == 8
    assert len(concern["references"]) == 3
    assert len(concern["blast_radius"]) == 8
    assert len(finalized["evidence"][0]["facts"]) == 8
    assert finalized["signals"][0]["metrics"]["by_path"] == {
        f"src/{index:02d}.py": index
        for index in range(12)
    }
    truncation = finalized["artifacts"]["payload_truncation"]
    assert {item["field"] for item in truncation["concerns"]} == {
        "evidence",
        "references",
        "blast_radius",
    }
    assert truncation["signals"] == [
        {"signal": "near_duplicate", "metric": "by_path", "original_total": 20, "kept": 12}
    ]
    assert finalized["summary"]["payload_bytes"] > 0


def test_code_review_payload_guard_keeps_small_result_metadata_clean(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["payload_bytes"] > 0
    assert "payload_truncation" not in result["artifacts"]


def test_code_review_payload_guard_does_not_change_concern_id() -> None:
    raw = {
        "mode": "code_review",
        "review_type": "full",
        "scores": {},
        "summary": {
            "headline": "Full code review complete",
            "concern_total": 1,
            "top_concern_total": 1,
            "concern_limit": 5,
            "signal_kinds": [],
        },
        "findings": [],
        "signals": [],
        "evidence": [],
        "concerns": [
            {
                "concern_id": "code-review:cleanup:abc123",
                "kind": "cleanup",
                "level": "caution",
                "confidence": 0.7,
                "location": {"path": "src/cleanup.py"},
                "root_cause": "test",
                "evidence": [f"fact={index}" for index in range(30)],
                "blast_radius": [f"src/file{index}.py" for index in range(30)],
            }
        ],
        "artifacts": {},
    }

    first = code_review._finalize_payload(copy.deepcopy(raw))
    second = code_review._finalize_payload(copy.deepcopy(raw))

    assert first["concerns"][0]["concern_id"] == "code-review:cleanup:abc123"
    assert second["concerns"][0]["concern_id"] == first["concerns"][0]["concern_id"]


def test_code_review_concerns_artifact_keeps_untruncated_generated_details(tmp_path, monkeypatch) -> None:
    long_concern = {
        "concern_id": "code-review:duplication:long",
        "kind": "duplication",
        "level": "caution",
        "confidence": 0.9,
        "location": {
            "path": "src/changed.py",
            "line": 2,
            "symbol": "changed",
            "symbol_kind": "function",
        },
        "root_cause": "test",
        "evidence": [f"near_duplicate.fact={index}" for index in range(20)],
        "references": [
            {"role": "reference", "path": f"src/ref{index}.py", "line": index}
            for index in range(5)
        ],
        "blast_radius": [f"src/blast{index}.py" for index in range(12)],
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())
    monkeypatch.setattr(
        code_review,
        "near_duplicate_scan",
        lambda *args, **kwargs: {"concerns": [long_concern], "candidate_total_before_scope": 1},
    )

    result = code_review.run_code_review_full(tmp_path)

    assert len(result["concerns"][0]["evidence"]) == 8
    artifact = json.loads(
        (tmp_path / ".architec" / "code-review-concerns.json").read_text(encoding="utf-8")
    )
    artifact_concern = artifact["concerns"][0]
    assert artifact["concern_total"] == 1
    assert len(artifact_concern["evidence"]) == 20
    assert len(artifact_concern["references"]) == 5
    assert len(artifact_concern["blast_radius"]) == 12


def test_code_review_full_writes_advisory_discovery_artifact_without_concerns(tmp_path, monkeypatch) -> None:
    (tmp_path / "locales.py").write_text(
        """
def thousands_separator(locale):
    value = locale.get("thousands")
    if value is None:
        return ","
    if value == "":
        return ","
    return str(value)


def decimal_separator(locale):
    value = locale.get("decimal")
    if value is None:
        return "."
    if value == "":
        return "."
    return str(value)
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["concern_total"] == 0
    assert result["concerns"] == []
    signal = next(item for item in result["signals"] if item["kind"] == "advisory_discovery")
    assert signal["metrics"]["candidate_total"] == 1
    assert signal["metrics"]["by_source"] == {"near_duplicate": 1}
    assert signal["metrics"]["by_reason"] == {"paired_api_variant": 1}
    artifact_path = Path(result["artifacts"]["code_review_discovery_json"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["summary"]["candidate_total"] == 1
    assert artifact["candidates"][0]["source"] == "near_duplicate"
    assert artifact["candidates"][0]["reason"] == "paired_api_variant"
    concerns_artifact = json.loads(
        Path(result["artifacts"]["code_review_concerns_json"]).read_text(encoding="utf-8")
    )
    assert concerns_artifact["concern_total"] == 0


def test_code_review_full_advisory_discovery_includes_module_shadow_dry_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())
    monkeypatch.setattr(code_review, "near_duplicate_scan", lambda *args, **kwargs: {"concerns": []})
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        code_review,
        "shadow_implementation_file_dry_run",
        lambda *args, **kwargs: {
            "mode": "dry_run",
            "candidate_total": 2,
            "pair_total": 1,
            "reported_total": 1,
            "candidates": [
                {
                    "left": {"path": "src/new_policy.py"},
                    "right": {"path": "src/existing_policy.py"},
                    "metrics": {"ast_similarity": 0.91},
                }
            ],
            "excluded_total": 0,
            "by_exclusion": {},
        },
    )

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["concern_total"] == 0
    signal = next(item for item in result["signals"] if item["kind"] == "advisory_discovery")
    assert signal["metrics"]["candidate_total"] == 1
    assert signal["metrics"]["by_source"] == {"shadow_implementation_file_dry_run": 1}
    assert signal["metrics"]["by_reason"] == {"module_shadow_candidate": 1}
    artifact = json.loads(
        Path(result["artifacts"]["code_review_discovery_json"]).read_text(encoding="utf-8")
    )
    assert artifact["candidates"][0]["source"] == "shadow_implementation_file_dry_run"
    assert artifact["candidates"][0]["reason"] == "module_shadow_candidate"


def test_code_review_full_reuses_near_duplicate_scan_for_discovery(tmp_path, monkeypatch) -> None:
    calls = {"count": 0}

    def fake_scan(*args, **kwargs):
        calls["count"] += 1
        return {
            "concerns": [],
            "candidate_total_before_scope": 1,
            "discovery": {
                "candidate_total": 1,
                "reported_total": 1,
                "by_reason": {"thin_wrapper_different_target": 1},
                "candidates": [
                    {
                        "source": "near_duplicate",
                        "reason": "thin_wrapper_different_target",
                        "location": {"path": "src/api.py", "symbol": "build_tree"},
                        "reference": {"path": "src/api.py", "symbol": "extract_signatures"},
                        "facts": ["near_duplicate.fingerprint=abc"],
                    }
                ],
            },
        }

    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())
    monkeypatch.setattr(code_review, "near_duplicate_scan", fake_scan)
    monkeypatch.setattr(
        code_review,
        "shadow_implementation_file_dry_run",
        lambda *args, **kwargs: {"candidates": []},
    )

    result = code_review.run_code_review_full(tmp_path)

    assert calls["count"] == 1
    signal = next(item for item in result["signals"] if item["kind"] == "advisory_discovery")
    assert signal["metrics"]["by_reason"] == {"thin_wrapper_different_target": 1}


def test_code_review_full_promotes_risk_reinforced_thin_wrapper_discovery(
    tmp_path,
    monkeypatch,
) -> None:
    risk_path = tmp_path / "risk.json"
    risk_path.write_text(
        json.dumps({"public_api_files": ["src/api.py"]}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())
    monkeypatch.setattr(
        code_review,
        "near_duplicate_scan",
        lambda *args, **kwargs: {
            "concerns": [],
            "candidate_total_before_scope": 1,
            "discovery": {
                "candidate_total": 1,
                "reported_total": 1,
                "by_reason": {"thin_wrapper_different_target": 1},
                "candidates": [
                    {
                        "source": "near_duplicate",
                        "reason": "thin_wrapper_different_target",
                        "location": {
                            "path": "src/api.py",
                            "line": 4,
                            "symbol": "build_tree",
                            "symbol_kind": "function",
                        },
                        "reference": {
                            "path": "src/api.py",
                            "line": 12,
                            "symbol": "extract_signatures",
                            "symbol_kind": "function",
                        },
                        "facts": ["near_duplicate.fingerprint=abc"],
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(
        code_review,
        "shadow_implementation_file_dry_run",
        lambda *args, **kwargs: {"candidates": []},
    )

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    assert result["summary"]["concern_total"] == 1
    assert result["summary"]["top_concern_total"] == 1
    concern = result["concerns"][0]
    assert concern["kind"] == "duplication"
    assert concern["level"] == "info"
    assert concern["location"]["path"] == "src/api.py"
    assert "advisory_discovery.reason=thin_wrapper_different_target" in concern["evidence"]
    assert "advisory_discovery.promoted_by=risk_context" in concern["evidence"]
    assert "advisory_discovery.reinforcement=public_api" in concern["evidence"]
    assert "risk_context.public_api=true" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "advisory_discovery")
    assert signal["metrics"]["candidate_total"] == 1
    assert signal["metrics"]["promoted_total"] == 1
    discovery_artifact = json.loads(
        Path(result["artifacts"]["code_review_discovery_json"]).read_text(encoding="utf-8")
    )
    assert discovery_artifact["summary"]["promoted_total"] == 1
    assert discovery_artifact["candidates"][0]["promoted"] is True
    concerns_artifact = json.loads(
        Path(result["artifacts"]["code_review_concerns_json"]).read_text(encoding="utf-8")
    )
    assert concerns_artifact["concern_total"] == 1
    assert "risk_context.public_api=true" in concerns_artifact["concerns"][0]["evidence"]


def test_code_review_full_does_not_promote_paired_api_discovery_with_risk_context(
    tmp_path,
    monkeypatch,
) -> None:
    risk_path = tmp_path / "risk.json"
    risk_path.write_text(
        json.dumps({"public_api_files": ["src/api.py"]}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())
    monkeypatch.setattr(
        code_review,
        "near_duplicate_scan",
        lambda *args, **kwargs: {
            "concerns": [],
            "candidate_total_before_scope": 1,
            "discovery": {
                "candidate_total": 1,
                "reported_total": 1,
                "by_reason": {"paired_api_variant": 1},
                "candidates": [
                    {
                        "source": "near_duplicate",
                        "reason": "paired_api_variant",
                        "location": {"path": "src/api.py", "symbol": "post"},
                        "reference": {"path": "src/api.py", "symbol": "dev"},
                        "facts": ["near_duplicate.fingerprint=abc"],
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(
        code_review,
        "shadow_implementation_file_dry_run",
        lambda *args, **kwargs: {"candidates": []},
    )

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    assert result["summary"]["concern_total"] == 0
    assert result["concerns"] == []
    signal = next(item for item in result["signals"] if item["kind"] == "advisory_discovery")
    assert signal["metrics"]["candidate_total"] == 1
    assert signal["metrics"]["promoted_total"] == 0
    artifact = json.loads(
        Path(result["artifacts"]["code_review_discovery_json"]).read_text(encoding="utf-8")
    )
    assert artifact["summary"]["promoted_total"] == 0
    assert "promoted" not in artifact["candidates"][0]


def test_run_code_review_static_full_uses_deterministic_signals_without_analysis(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))
    monkeypatch.setattr(
        code_review,
        "near_duplicate_scan",
        lambda *args, **kwargs: {
            "concerns": [],
            "candidate_total_before_scope": 1,
            "discovery": {
                "candidate_total": 1,
                "reported_total": 1,
                "by_reason": {"paired_api_variant": 1},
                "candidates": [
                    {
                        "source": "near_duplicate",
                        "reason": "paired_api_variant",
                        "location": {"path": "src/api.py", "symbol": "post"},
                        "reference": {"path": "src/api.py", "symbol": "dev"},
                        "facts": ["near_duplicate.fingerprint=abc"],
                    }
                ],
            },
        },
    )
    monkeypatch.setattr(code_review, "shadow_implementation_scan", lambda *args, **kwargs: {"concerns": []})
    monkeypatch.setattr(
        code_review,
        "shadow_implementation_file_dry_run",
        lambda *args, **kwargs: {"candidates": []},
    )

    result = code_review.run_code_review_static_full(tmp_path, reason="backend unavailable")

    assert result["mode"] == "code_review"
    assert result["review_type"] == "full"
    assert result["summary"]["headline"] == "Full analysis was unavailable; static code-review signals were generated."
    assert result["summary"]["analysis_mode"] == "static"
    assert result["summary"]["reason"] == "backend unavailable"
    assert result["summary"]["concern_total"] == 0
    assert result["artifacts"]["code_review_analysis_mode"] == "static"
    assert result["artifacts"]["code_review_static_reason"] == "backend unavailable"
    signal = next(item for item in result["signals"] if item["kind"] == "advisory_discovery")
    assert signal["metrics"]["by_reason"] == {"paired_api_variant": 1}
    assert "code_review_discovery_json" in result["artifacts"]


def test_run_code_review_static_diff_uses_changed_file_scope_without_analysis(
    tmp_path,
    monkeypatch,
) -> None:
    _write_near_duplicate_project(tmp_path)
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))
    monkeypatch.setattr(
        code_review,
        "git_changed_files",
        lambda *args, **kwargs: [{"path": "src/changed.py", "added": 4, "deleted": 1}],
    )

    result = code_review.run_code_review_static_diff(tmp_path, reason="backend unavailable")

    assert result["mode"] == "code_review"
    assert result["review_type"] == "diff"
    assert result["summary"]["headline"] == "Diff analysis was unavailable; static code-review signals were generated."
    assert result["summary"]["analysis_mode"] == "static"
    assert result["summary"]["reason"] == "backend unavailable"
    assert result["summary"]["concern_total"] == 1
    assert result["summary"]["scoped_concern_total"] == 1
    assert result["summary"]["global_context_concern_total"] == 0
    assert result["artifacts"]["code_review_analysis_mode"] == "static"
    assert result["artifacts"]["code_review_static_reason"] == "backend unavailable"
    assert [item["kind"] for item in result["concerns"]] == ["duplication"]
    signal = next(item for item in result["signals"] if item["kind"] == "near_duplicate")
    assert signal["metrics"]["scoped_to_changed_files"] is True


def test_run_code_review_incremental_llm_uses_selected_scope_without_full_analysis(
    tmp_path,
    monkeypatch,
) -> None:
    _write_near_duplicate_project(tmp_path)
    calls: list[object] = []
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))
    monkeypatch.setattr(
        code_review,
        "git_changed_files",
        lambda *args, **kwargs: [{"path": "src/changed.py", "added": 4, "deleted": 1}],
    )

    def fake_llm(root: Path, *, payload: dict[str, object]) -> dict[str, object]:
        calls.append((root, payload))
        return {
            "headline": "Incremental architecture review complete",
            "executive_summary": "The selected change repeats an existing implementation shape.",
            "top_takeaways": ["Review whether the changed helper should reuse the existing one."],
            "recommendations": [
                {
                    "priority": "P1",
                    "title": "Compare duplicate helper intent",
                    "why": "The selected file matches an existing implementation shape.",
                }
            ],
        }

    monkeypatch.setattr(code_review, "incremental_llm_summary", fake_llm)

    result = code_review.run_code_review_incremental_llm(tmp_path)

    assert calls
    llm_payload = calls[0][1]
    assert llm_payload["analysis_context"] == "selected_scope"
    assert llm_payload["changed_files"] == ["src/changed.py"]
    assert result["mode"] == "code_review"
    assert result["review_type"] == "diff"
    assert result["summary"]["headline"] == "Incremental architecture review complete"
    assert result["summary"]["analysis_mode"] == "incremental_llm"
    assert result["summary"]["llm_context"] == "selected_scope"
    assert result["summary"]["executive_summary"] == "The selected change repeats an existing implementation shape."
    assert result["recommendations"][0]["title"] == "Compare duplicate helper intent"
    assert result["artifacts"]["code_review_analysis_mode"] == "incremental_llm"
    assert result["artifacts"]["code_review_llm_context"] == "selected_scope"
    signal = next(item for item in result["signals"] if item["kind"] == "cost_context")
    assert signal["metrics"]["selected_file_total"] == 1
    assert signal["metrics"]["llm_call_total"] == 1
    assert signal["metrics"]["cache_hit_total"] == 0
    assert signal["metrics"]["llm_cache_hit_total"] == 0
    assert signal["metrics"]["llm_backend_call_total"] == 1
    assert signal["metrics"]["llm_context"] == "selected_scope"


def test_run_code_review_incremental_llm_reports_summary_cache_hit(
    tmp_path,
    monkeypatch,
) -> None:
    _write_near_duplicate_project(tmp_path)
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))
    monkeypatch.setattr(
        code_review,
        "git_changed_files",
        lambda *args, **kwargs: [{"path": "src/changed.py", "added": 4, "deleted": 1}],
    )
    monkeypatch.setattr(
        code_review,
        "incremental_llm_summary",
        lambda *args, **kwargs: {
            "headline": "Incremental architecture review complete",
            "_cache_hit": True,
        },
    )

    result = code_review.run_code_review_incremental_llm(tmp_path)

    signal = next(item for item in result["signals"] if item["kind"] == "cost_context")
    assert signal["metrics"]["llm_call_total"] == 1
    assert signal["metrics"]["cache_hit_total"] == 1
    assert signal["metrics"]["llm_cache_hit_total"] == 1
    assert signal["metrics"]["llm_backend_call_total"] == 0


def test_run_code_review_incremental_llm_reports_stale_snapshot_without_refresh(
    tmp_path,
    monkeypatch,
) -> None:
    _write_near_duplicate_project(tmp_path)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))
    monkeypatch.setattr(
        code_review,
        "git_changed_files",
        lambda *args, **kwargs: [{"path": "src/changed.py", "added": 4, "deleted": 1}],
    )
    hippo = tmp_path / ".hippocampus"
    hippo.mkdir()
    for name in (
        "architect-metrics.json",
        "hippocampus-index.json",
        "code-signatures.json",
        "structure-prompt.md",
    ):
        (hippo / name).write_text("{}\n", encoding="utf-8")
    (hippo / "bundle-state.json").write_text(
        json.dumps({"generated_at": "2000-01-01T00:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )

    def fake_llm(root: Path, *, payload: dict[str, object]) -> dict[str, object]:
        calls.append(payload)
        return {"headline": "Incremental architecture review complete"}

    monkeypatch.setattr(code_review, "incremental_llm_summary", fake_llm)

    result = code_review.run_code_review_incremental_llm(tmp_path)

    snapshot_payload = calls[0]["snapshot_context"]
    assert snapshot_payload["hippo_bundle_present"] is True
    assert snapshot_payload["hippo_bundle_stale"] is True
    assert snapshot_payload["hippo_refresh_performed"] is False
    assert snapshot_payload["selected_changed_after_bundle_total"] == 1
    signal = next(item for item in result["signals"] if item["kind"] == "snapshot_context")
    assert signal["metrics"]["hippo_bundle_present"] is True
    assert signal["metrics"]["hippo_bundle_stale"] is True
    assert signal["metrics"]["hippo_refresh_performed"] is False
    assert signal["metrics"]["stale_reason_total"] == 1
    assert signal["metrics"]["selected_changed_after_bundle_total"] == 1
    assert result["summary"]["analysis_mode"] == "incremental_llm"


def test_run_code_review_incremental_llm_reports_missing_snapshot_without_refresh(
    tmp_path,
    monkeypatch,
) -> None:
    _write_near_duplicate_project(tmp_path)
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))
    monkeypatch.setattr(
        code_review,
        "git_changed_files",
        lambda *args, **kwargs: [{"path": "src/changed.py", "added": 4, "deleted": 1}],
    )
    monkeypatch.setattr(
        code_review,
        "incremental_llm_summary",
        lambda *args, **kwargs: {"headline": "Incremental architecture review complete"},
    )

    result = code_review.run_code_review_incremental_llm(tmp_path)

    signal = next(item for item in result["signals"] if item["kind"] == "snapshot_context")
    assert signal["metrics"]["hippo_bundle_present"] is False
    assert signal["metrics"]["hippo_bundle_stale"] is False
    assert signal["metrics"]["missing_file_total"] > 0
    assert "without a Hippos structure snapshot" in signal["summary"]


def test_run_code_review_incremental_llm_snapshot_context_is_selected_file_scoped(
    tmp_path,
    monkeypatch,
) -> None:
    _write_near_duplicate_project(tmp_path)
    hippo = tmp_path / ".hippocampus"
    hippo.mkdir()
    for name in (
        "architect-metrics.json",
        "hippocampus-index.json",
        "code-signatures.json",
        "structure-prompt.md",
    ):
        (hippo / name).write_text("{}\n", encoding="utf-8")
    generated_at = datetime.now(timezone.utc).isoformat()
    (hippo / "bundle-state.json").write_text(
        json.dumps({"generated_at": generated_at}) + "\n",
        encoding="utf-8",
    )
    unselected = tmp_path / "src" / "unselected.py"
    unselected.write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))
    monkeypatch.setattr(
        code_review,
        "git_changed_files",
        lambda *args, **kwargs: [{"path": "src/changed.py", "added": 4, "deleted": 1}],
    )
    monkeypatch.setattr(
        code_review,
        "incremental_llm_summary",
        lambda *args, **kwargs: {"headline": "Incremental architecture review complete"},
    )

    result = code_review.run_code_review_incremental_llm(tmp_path)

    signal = next(item for item in result["signals"] if item["kind"] == "snapshot_context")
    assert signal["metrics"]["hippo_bundle_present"] is True
    assert signal["metrics"]["hippo_bundle_stale"] is False
    assert signal["metrics"]["selected_changed_after_bundle_total"] == 0


def test_run_code_review_incremental_llm_reports_unknown_snapshot_freshness(
    tmp_path,
    monkeypatch,
) -> None:
    _write_near_duplicate_project(tmp_path)
    hippo = tmp_path / ".hippocampus"
    hippo.mkdir()
    for name in (
        "architect-metrics.json",
        "hippocampus-index.json",
        "code-signatures.json",
        "structure-prompt.md",
    ):
        (hippo / name).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))
    monkeypatch.setattr(
        code_review,
        "git_changed_files",
        lambda *args, **kwargs: [{"path": "src/changed.py", "added": 4, "deleted": 1}],
    )
    monkeypatch.setattr(
        code_review,
        "incremental_llm_summary",
        lambda *args, **kwargs: {"headline": "Incremental architecture review complete"},
    )

    result = code_review.run_code_review_incremental_llm(tmp_path)

    signal = next(item for item in result["signals"] if item["kind"] == "snapshot_context")
    assert signal["metrics"]["hippo_bundle_present"] is True
    assert signal["metrics"]["hippo_bundle_stale"] is False
    assert signal["metrics"]["freshness_unknown"] is True
    assert signal["metrics"]["selected_changed_after_bundle_total"] == 0
    assert "freshness could not be determined" in signal["summary"]


def test_run_code_review_static_since_bad_ref_returns_degraded_range_result(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: pytest.fail("analysis should not run"))

    def raise_bad_ref(*args, **kwargs):
        raise RuntimeError("git range error while running `git diff --numstat missing...HEAD`: fatal: bad revision")

    monkeypatch.setattr(code_review, "git_changed_files", raise_bad_ref)

    result = code_review.run_code_review_static_since(
        tmp_path,
        ref="missing",
        reason="backend unavailable",
    )

    assert result["review_type"] == "since"
    assert result["summary"]["headline"] == "Unable to analyze the requested since range."
    assert result["summary"]["concern_total"] == 0
    assert result["signals"] == []
    assert result["concerns"] == []


def test_code_review_concerns_artifact_write_os_error_is_fail_open(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())

    def raise_os_error(*args, **kwargs):
        raise OSError("artifact disk full")

    monkeypatch.setattr(code_review, "write_json", raise_os_error)

    result = code_review.run_code_review_full(tmp_path)

    assert result["mode"] == "code_review"
    assert result["artifacts"]["code_review_concerns_error"] == "artifact disk full"
    assert "code_review_concerns_json" not in result["artifacts"]


def test_code_review_concerns_artifact_non_os_error_is_not_swallowed(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())

    def raise_bug(*args, **kwargs):
        raise ValueError("artifact serialization bug")

    monkeypatch.setattr(code_review, "write_json", raise_bug)

    with pytest.raises(ValueError, match="artifact serialization bug"):
        code_review.run_code_review_full(tmp_path)


def test_code_review_diff_and_since_write_concerns_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())

    diff_result = code_review.run_code_review_diff(tmp_path)
    since_result = code_review.run_code_review_since(tmp_path, ref="main")

    artifact_path = tmp_path / ".architec" / "code-review-concerns.json"
    assert diff_result["artifacts"]["code_review_concerns_json"] == str(artifact_path)
    assert since_result["artifacts"]["code_review_concerns_json"] == str(artifact_path)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["review_type"] == "since"
    assert artifact["concerns"] == []


def test_code_review_file_concern_ids_are_stable_across_candidate_order(tmp_path, monkeypatch) -> None:
    report_a = {
        "scores": {},
        "summary": {},
        "cleanup": {
            "candidate_total": 2,
            "review_required_total": 2,
            "top_candidates": [
                {"path": "src/a.py", "category": "legacy", "confidence": 0.92},
                {"path": "src/b.py", "category": "legacy", "confidence": 0.91},
            ],
        },
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [],
        "topology": {},
        "artifacts": {},
    }
    report_b = copy.deepcopy(report_a)
    report_b["cleanup"]["top_candidates"] = list(reversed(report_b["cleanup"]["top_candidates"]))
    reports = [report_a, report_b]
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: reports.pop(0))
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    first = code_review.run_code_review_full(tmp_path)
    second = code_review.run_code_review_full(tmp_path)

    first_ids = {item["location"]["path"]: item["concern_id"] for item in first["concerns"]}
    second_ids = {item["location"]["path"]: item["concern_id"] for item in second["concerns"]}
    assert first_ids == second_ids
    assert first_ids["src/a.py"].startswith("code-review:cleanup:")
    assert len(first_ids["src/a.py"].rsplit(":", 1)[1]) == 12


def test_run_code_review_full_non_numeric_confidence_uses_defaults(tmp_path, monkeypatch) -> None:
    report = {
        **_analysis_report(),
        "cleanup": {
            "candidate_total": 1,
            "review_required_total": 1,
            "top_candidates": [{"path": "src/cleanup.py", "category": "legacy", "confidence": "high"}],
        },
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [{"path": "src/hotspot.py", "confidence": {"score": 1}}],
        "topology": {
            "needs_folder_management": True,
            "flat_file_total": 2,
            "confidence": "medium",
            "root_placement_review": {
                "review_root_files": [{"path": "src/topology.py"}],
            },
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_full(tmp_path)

    confidence_by_path = {
        item["location"]["path"]: item["confidence"]
        for item in result["concerns"]
    }
    assert confidence_by_path["src/cleanup.py"] == 0.5
    assert confidence_by_path["src/hotspot.py"] == 0.7
    assert confidence_by_path["src/topology.py"] == 0.6


def test_code_review_signals_use_uniform_schema(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path)

    assert result["summary"]["signal_kinds"] == ["cleanup", "archive", "semantic_judge", "hotspot", "topology"]
    for signal in result["signals"]:
        assert set(signal) == {"kind", "summary", "metrics"}
        assert isinstance(signal["summary"], str)
        assert isinstance(signal["metrics"], dict)
    cleanup = next(signal for signal in result["signals"] if signal["kind"] == "cleanup")
    assert cleanup["metrics"] == {
        "candidate_total": 1,
        "review_required_total": 1,
        "owner_total": 1,
        "ttl_total": 1,
        "expires_total": 1,
        "expired_total": 0,
        "by_category": {"legacy_impl": 1},
    }
    archive = next(signal for signal in result["signals"] if signal["kind"] == "archive")
    assert archive["metrics"] == {
        "candidate_total": 1,
        "ready_total": 1,
        "review_total": 0,
        "by_tier": {"ready": 1},
        "by_category": {"stale_doc": 1},
    }
    semantic_judge = next(signal for signal in result["signals"] if signal["kind"] == "semantic_judge")
    assert semantic_judge["metrics"] == {
        "status": "ok",
        "reviewed_total": 1,
        "candidate_pool_total": 2,
        "by_decision": {"archive_first": 1},
    }
    hotspot = next(signal for signal in result["signals"] if signal["kind"] == "hotspot")
    assert hotspot["metrics"] == {"item_total": 1}
    topology = next(signal for signal in result["signals"] if signal["kind"] == "topology")
    assert topology["metrics"] == {"needs_folder_management": True, "flat_file_total": 12}


def test_code_review_evidence_index_is_derived_from_displayed_concerns(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path)

    assert len(result["evidence"]) == len(result["concerns"])
    for index, item in enumerate(result["evidence"], start=1):
        concern = result["concerns"][index - 1]
        assert item == {
            "evidence_id": f"code-review:evidence:{index}",
            "concern_id": concern["concern_id"],
            "kind": concern["kind"],
            "location": concern["location"],
            "confidence": concern["confidence"],
            "facts": concern["evidence"],
        }


def test_code_review_full_adds_near_duplicate_signal_and_concern(tmp_path, monkeypatch) -> None:
    report = {
        **_analysis_report(),
        "cleanup": {},
        "hotspots": [],
        "topology": {},
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)
    monkeypatch.setattr(
        code_review,
        "near_duplicate_scan",
        lambda *args, **kwargs: {
            "concerns": [
                {
                    "concern_id": "code-review:near-duplicate:1",
                    "kind": "duplication",
                    "level": "caution",
                    "confidence": 0.9,
                    "location": {
                        "path": "src/b.py",
                        "line": 2,
                        "symbol": "second",
                        "symbol_kind": "function",
                    },
                    "root_cause": "Function has the same normalized AST fingerprint as another function.",
                    "evidence": ["near_duplicate.fingerprint=abc", "near_duplicate.reference=src/a.py:2:first"],
                    "references": [
                        {
                            "role": "reference",
                            "path": "src/a.py",
                            "line": 2,
                            "symbol": "first",
                            "symbol_kind": "function",
                        }
                    ],
                    "blast_radius": ["src/b.py", "src/a.py"],
                    "next_steps_hint": "Review whether one implementation can reuse or call the other.",
                }
            ],
            "candidate_total_before_scope": 1,
        },
    )

    result = code_review.run_code_review_full(tmp_path)

    assert result["concerns"][0]["kind"] == "duplication"
    assert result["concerns"][0]["references"][0]["path"] == "src/a.py"
    signal = next(item for item in result["signals"] if item["kind"] == "near_duplicate")
    assert signal["metrics"] == {"concern_total": 1}


def test_code_review_diff_adds_changed_file_scoped_near_duplicate_signal(tmp_path, monkeypatch) -> None:
    _write_near_duplicate_project(tmp_path)
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/changed.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    concern = next(item for item in result["concerns"] if item["kind"] == "duplication")
    assert concern["location"]["path"] == "src/changed.py"
    assert concern["references"][0]["path"] == "src/existing.py"
    signal = next(item for item in result["signals"] if item["kind"] == "near_duplicate")
    assert signal["summary"] == "1 near-duplicate function concerns detected in changed files."
    assert signal["metrics"]["concern_total"] == 1
    assert signal["metrics"]["scoped_to_changed_files"] is True
    assert signal["metrics"]["changed_file_total"] == 1
    assert signal["metrics"]["candidate_total_before_scope"] == 1
    assert signal["metrics"]["scan_cache"] == {
        "file_total": 2,
        "file_cache_hit_total": 0,
        "file_cache_miss_total": 2,
    }


def test_code_review_since_adds_changed_file_scoped_near_duplicate_signal(tmp_path, monkeypatch) -> None:
    _write_near_duplicate_project(tmp_path)
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/changed.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_since(tmp_path, ref="main")

    concern = next(item for item in result["concerns"] if item["kind"] == "duplication")
    assert concern["location"]["path"] == "src/changed.py"
    assert concern["references"][0]["path"] == "src/existing.py"
    signal = next(item for item in result["signals"] if item["kind"] == "near_duplicate")
    assert signal["metrics"]["scoped_to_changed_files"] is True
    assert signal["metrics"]["changed_file_total"] == 1


def test_code_review_diff_without_scoped_near_duplicate_omits_signal(tmp_path, monkeypatch) -> None:
    _write_near_duplicate_project(tmp_path)
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/unrelated.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    assert all(item["kind"] != "duplication" for item in result["concerns"])
    assert all(item["kind"] != "near_duplicate" for item in result["signals"])


def test_code_review_diff_adds_changed_file_architecture_contract_concern(tmp_path, monkeypatch) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.architecture_contracts]]",
                'id = "api-no-storage"',
                'source_glob = "src/api/**"',
                'owner = "api-platform"',
                'restricted_imports = ["app.storage"]',
                'note = "Use the service facade."',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text(
        "from app.storage import repository\n\n\ndef handle():\n    return repository.load()\n",
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    concern = next(item for item in result["concerns"] if item["kind"] == "architecture-contract")
    assert concern["location"]["path"] == "src/api/handler.py"
    assert concern["location"]["line"] == 1
    assert "architecture_contract.rule_id=api-no-storage" in concern["evidence"]
    assert "architecture_contract.import=app.storage" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "architecture_contract")
    assert signal["summary"] == "1 architecture contract concerns detected in changed files."
    assert signal["metrics"] == {
        "rule_total": 1,
        "checked_file_total": 1,
        "concern_total": 1,
        "concern_total_before_limit": 1,
        "scoped_to_changed_files": True,
    }


def test_code_review_since_adds_changed_file_architecture_contract_concern(tmp_path, monkeypatch) -> None:
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[[archi.architecture_contracts]]",
                'id = "domain-no-cli"',
                'source_glob = "src/domain/**"',
                'restricted_imports = ["app.cli"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    domain_dir = tmp_path / "src" / "domain"
    domain_dir.mkdir(parents=True)
    (domain_dir / "model.py").write_text("import app.cli\n", encoding="utf-8")
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/domain/model.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_since(tmp_path, ref="main")

    assert result["review_type"] == "since"
    concern = next(item for item in result["concerns"] if item["kind"] == "architecture-contract")
    assert concern["location"]["path"] == "src/domain/model.py"
    assert "architecture_contract.import=app.cli" in concern["evidence"]


def test_code_review_architecture_contracts_stay_empty_without_config(tmp_path, monkeypatch) -> None:
    source_dir = tmp_path / "src" / "api"
    source_dir.mkdir(parents=True)
    (source_dir / "handler.py").write_text("import app.storage\n", encoding="utf-8")
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path)

    assert all(item["kind"] != "architecture-contract" for item in result["concerns"])
    assert all(item["kind"] != "architecture_contract" for item in result["signals"])


def test_code_review_since_bad_ref_does_not_run_architecture_contract_scan(tmp_path, monkeypatch) -> None:
    def raise_bad_ref(*args, **kwargs):
        raise RuntimeError("git range error while running `git diff --numstat missing...HEAD`: fatal: bad revision")

    def fail_contract_scan(*args, **kwargs):
        raise AssertionError("architecture contract scan should not run")

    monkeypatch.setattr(code_review, "run_analysis", raise_bad_ref)
    monkeypatch.setattr(code_review, "architecture_contract_scan", fail_contract_scan)

    result = code_review.run_code_review_since(tmp_path, ref="missing")

    assert result["review_type"] == "since"
    assert result["concerns"] == []
    assert result["signals"] == []


def test_code_review_diff_adds_plan_diff_consistency_concerns(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [
                        {"path": "src/api/handler.py", "intent": "adjust API behavior"},
                        {"path": "src/service/model.py", "intent": "update service model"},
                    ],
                    "dependencies": [],
                },
                "plan_fingerprint": "abc123",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 2,
            "changed_files": ["src/api/handler.py", "src/infra/cache.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    plan_concerns = [item for item in result["concerns"] if item["kind"] == "plan-diff-consistency"]
    assert {item["location"]["path"] for item in plan_concerns} == {
        "src/infra/cache.py",
        "src/service/model.py",
    }
    assert any(
        "plan_diff_consistency.observation=unexpected_changed_file" in item["evidence"]
        for item in plan_concerns
    )
    assert any(
        "plan_diff_consistency.observation=planned_path_not_changed" in item["evidence"]
        for item in plan_concerns
    )
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["summary"] == "2 plan/diff consistency observations detected."
    assert signal["metrics"] == {
        "planned_path_total": 2,
        "planned_import_total": 0,
        "planned_import_alternative_total": 0,
        "observed_planned_import_total": 0,
        "missing_planned_import_total": 0,
        "expected_test_total": 0,
        "observed_expected_test_total": 0,
        "missing_expected_test_total": 0,
        "public_api_migration_total": 0,
        "observed_public_api_migration_total": 0,
        "missing_public_api_migration_total": 0,
        "semantic_intent_total": 0,
        "observed_semantic_intent_total": 0,
        "missing_semantic_intent_total": 0,
        "conflicting_semantic_intent_total": 0,
        "changed_file_total": 2,
        "concern_total": 2,
        "concern_total_before_limit": 2,
        "scoped_to_changed_files": True,
    }


def test_code_review_diff_with_plan_and_empty_diff_reports_missing_planned_path(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/service/model.py", "intent": "update model"}],
                    "dependencies": [],
                },
                "plan_fingerprint": "empty-diff-plan",
                "artifacts": {"plan_path": "plans/model.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 0,
            "changed_files": [],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concern = next(item for item in result["concerns"] if item["kind"] == "plan-diff-consistency")
    assert concern["location"]["path"] == "src/service/model.py"
    assert "plan_diff_consistency.observation=planned_path_not_changed" in concern["evidence"]
    assert "plan_diff_consistency.changed_file_total=0" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"] == {
        "planned_path_total": 1,
        "planned_import_total": 0,
        "planned_import_alternative_total": 0,
        "observed_planned_import_total": 0,
        "missing_planned_import_total": 0,
        "expected_test_total": 0,
        "observed_expected_test_total": 0,
        "missing_expected_test_total": 0,
        "public_api_migration_total": 0,
        "observed_public_api_migration_total": 0,
        "missing_public_api_migration_total": 0,
        "semantic_intent_total": 0,
        "observed_semantic_intent_total": 0,
        "missing_semantic_intent_total": 0,
        "conflicting_semantic_intent_total": 0,
        "changed_file_total": 0,
        "concern_total": 1,
        "concern_total_before_limit": 1,
        "scoped_to_changed_files": True,
    }
    assert result["summary"]["scoped_concern_total"] == 1
    assert result["summary"]["global_context_concern_total"] == 0
    assert result["summary"]["top_concern_total"] == 1


def test_code_review_diff_adds_plan_import_expectation_concern(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py", "intent": "route through service facade"}],
                    "dependencies": [
                        {
                            "source": "src/api/**",
                            "imports": ["app.service.facade"],
                        }
                    ],
                },
                "plan_fingerprint": "import-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("import app.storage\n", encoding="utf-8")
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concern = next(
        item
        for item in result["concerns"]
        if item["kind"] == "plan-diff-consistency"
        and "plan_diff_consistency.observation=planned_import_not_observed" in item["evidence"]
    )
    assert concern["location"]["path"] == "src/api/handler.py"
    assert "plan_diff_consistency.planned_import=app.service.facade" in concern["evidence"]
    assert "plan_diff_consistency.dependency_source=src/api/**" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["planned_import_total"] == 1
    assert signal["metrics"]["planned_import_alternative_total"] == 0
    assert signal["metrics"]["observed_planned_import_total"] == 0
    assert signal["metrics"]["missing_planned_import_total"] == 1
    assert signal["metrics"]["concern_total"] == 1


def test_code_review_diff_observes_plan_import_expectation(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py", "intent": "route through service facade"}],
                    "dependencies": [{"path": "src/api/handler.py", "module": "app.service.facade"}],
                },
                "plan_fingerprint": "observed-import-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("from app.service import facade\n", encoding="utf-8")
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    encoded = json.dumps(result, sort_keys=True)
    assert "planned_import_not_observed" not in encoded
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["planned_import_total"] == 1
    assert signal["metrics"]["observed_planned_import_total"] == 1
    assert signal["metrics"]["missing_planned_import_total"] == 0
    assert signal["metrics"]["concern_total"] == 0


def test_code_review_diff_observes_plan_import_alternative_expectation(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py", "intent": "route through a service boundary"}],
                    "dependencies": [
                        {
                            "source": "src/api/**",
                            "any_of": ["app.service.facade", "app.service.gateway"],
                        }
                    ],
                },
                "plan_fingerprint": "observed-alternative-import-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("from app.service import gateway\n", encoding="utf-8")
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    encoded = json.dumps(result, sort_keys=True)
    assert "planned_import_alternative_not_observed" not in encoded
    assert "planned_import_not_observed" not in encoded
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["planned_import_total"] == 1
    assert signal["metrics"]["planned_import_alternative_total"] == 1
    assert signal["metrics"]["observed_planned_import_total"] == 1
    assert signal["metrics"]["missing_planned_import_total"] == 0
    assert signal["metrics"]["concern_total"] == 0


def test_code_review_diff_missing_plan_import_alternatives_emit_single_concern(
    tmp_path,
    monkeypatch,
) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py", "intent": "route through a service boundary"}],
                    "dependencies": [
                        {
                            "source": "src/api/**",
                            "alternatives": ["app.service.facade", "app.service.gateway"],
                        }
                    ],
                },
                "plan_fingerprint": "missing-alternative-import-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("import app.storage\n", encoding="utf-8")
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concerns = [
        item
        for item in result["concerns"]
        if item["kind"] == "plan-diff-consistency"
        and "plan_diff_consistency.observation=planned_import_alternative_not_observed" in item["evidence"]
    ]
    assert len(concerns) == 1
    concern = concerns[0]
    assert concern["location"]["path"] == "src/api/handler.py"
    assert "plan_diff_consistency.planned_import_alternatives=app.service.facade,app.service.gateway" in concern["evidence"]
    assert "plan_diff_consistency.planned_import_alternative_total=2" in concern["evidence"]
    assert "plan_diff_consistency.dependency_source=src/api/**" in concern["evidence"]
    assert "plan_diff_consistency.planned_import=app.service.facade" not in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["planned_import_total"] == 1
    assert signal["metrics"]["planned_import_alternative_total"] == 1
    assert signal["metrics"]["observed_planned_import_total"] == 0
    assert signal["metrics"]["missing_planned_import_total"] == 1
    assert signal["metrics"]["concern_total"] == 1
    payload = json.dumps(result, sort_keys=True).lower()
    for term in ("pass", "fail", "block", "verdict", "must-fix", "patch", "apply"):
        assert term not in payload


def test_code_review_diff_ignores_string_dependencies_for_import_expectations(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py", "intent": "route handler"}],
                    "dependencies": ["src/service/contracts.py"],
                },
                "plan_fingerprint": "string-dependency-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "handler.py").write_text("VALUE = 1\n", encoding="utf-8")
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    encoded = json.dumps(result, sort_keys=True)
    assert "planned_import_not_observed" not in encoded
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["planned_import_total"] == 0
    assert signal["metrics"]["planned_import_alternative_total"] == 0
    assert signal["metrics"]["observed_planned_import_total"] == 0
    assert signal["metrics"]["missing_planned_import_total"] == 0
    assert signal["metrics"]["concern_total"] == 0


def test_code_review_diff_ignores_plan_import_expectation_without_changed_python_file(
    tmp_path, monkeypatch
) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/schema.yaml", "intent": "update schema"}],
                    "dependencies": [{"source": "src/api/**", "imports": ["app.service.facade"]}],
                },
                "plan_fingerprint": "non-python-dependency-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    api_dir = tmp_path / "src" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "schema.yaml").write_text("version: 1\n", encoding="utf-8")
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/schema.yaml"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    encoded = json.dumps(result, sort_keys=True)
    assert "planned_import_not_observed" not in encoded
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["planned_import_total"] == 1
    assert signal["metrics"]["planned_import_alternative_total"] == 0
    assert signal["metrics"]["observed_planned_import_total"] == 0
    assert signal["metrics"]["missing_planned_import_total"] == 0
    assert signal["metrics"]["concern_total"] == 0


def test_code_review_diff_adds_missing_expected_test_concern(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py", "intent": "route handler"}],
                    "expected_tests": [
                        {
                            "test_path": "tests/test_api_handler.py",
                            "source": "src/api/**",
                        }
                    ],
                },
                "plan_fingerprint": "expected-test-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concern = next(
        item
        for item in result["concerns"]
        if item["kind"] == "plan-diff-consistency"
        and "plan_diff_consistency.observation=planned_test_not_observed" in item["evidence"]
    )
    assert concern["location"]["path"] == "tests/test_api_handler.py"
    assert "plan_diff_consistency.expected_test=tests/test_api_handler.py" in concern["evidence"]
    assert "plan_diff_consistency.test_source=src/api/**" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["expected_test_total"] == 1
    assert signal["metrics"]["observed_expected_test_total"] == 0
    assert signal["metrics"]["missing_expected_test_total"] == 1
    assert signal["metrics"]["concern_total"] == 1


def test_code_review_diff_observes_expected_test_path(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py", "intent": "route handler"}],
                    "tests": [{"glob": "tests/test_api_*.py", "source_glob": "src/api/**"}],
                },
                "plan_fingerprint": "observed-test-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 2,
            "changed_files": ["src/api/handler.py", "tests/test_api_handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    encoded = json.dumps(result, sort_keys=True)
    assert "planned_test_not_observed" not in encoded
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["expected_test_total"] == 1
    assert signal["metrics"]["observed_expected_test_total"] == 1
    assert signal["metrics"]["missing_expected_test_total"] == 0
    assert signal["metrics"]["concern_total"] == 0


def test_code_review_diff_empty_diff_reports_missing_expected_test(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "expected_tests": [{"test_glob": "tests/test_service_model.py"}],
                },
                "plan_fingerprint": "empty-diff-test-plan",
                "artifacts": {"plan_path": "plans/model.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 0,
            "changed_files": [],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concern = next(item for item in result["concerns"] if item["kind"] == "plan-diff-consistency")
    assert concern["location"]["path"] == "tests/test_service_model.py"
    assert "plan_diff_consistency.observation=planned_test_not_observed" in concern["evidence"]
    assert "plan_diff_consistency.changed_file_total=0" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["expected_test_total"] == 1
    assert signal["metrics"]["observed_expected_test_total"] == 0
    assert signal["metrics"]["missing_expected_test_total"] == 1
    assert signal["metrics"]["concern_total"] == 1


def test_code_review_diff_ignores_string_expected_tests(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "expected_tests": ["tests/test_api_handler.py"],
                    "tests": ["tests/test_service_model.py"],
                },
                "plan_fingerprint": "string-test-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 0,
            "changed_files": [],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    assert result["concerns"] == []
    assert result["signals"] == []


def test_code_review_diff_adds_missing_public_api_migration_concern(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "public_api_migrations": [
                        {
                            "public_api_path": "src/api/__init__.py",
                            "symbol": "build_tree",
                            "old_symbol": "build_tree",
                            "new_symbol": "build_project_tree",
                            "source": "src/api/**",
                        }
                    ],
                },
                "plan_fingerprint": "api-migration-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/core/tree.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concern = next(
        item
        for item in result["concerns"]
        if item["kind"] == "plan-diff-consistency"
        and "plan_diff_consistency.observation=planned_public_api_migration_not_observed"
        in item["evidence"]
    )
    assert concern["location"] == {
        "path": "src/api/__init__.py",
        "line": 0,
        "symbol": "build_tree",
        "symbol_kind": "module",
    }
    assert "plan_diff_consistency.public_api_migration=src/api/__init__.py" in concern["evidence"]
    assert "plan_diff_consistency.symbol=build_tree" in concern["evidence"]
    assert "plan_diff_consistency.old_symbol=build_tree" in concern["evidence"]
    assert "plan_diff_consistency.new_symbol=build_project_tree" in concern["evidence"]
    assert "plan_diff_consistency.migration_source=src/api/**" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["public_api_migration_total"] == 1
    assert signal["metrics"]["observed_public_api_migration_total"] == 0
    assert signal["metrics"]["missing_public_api_migration_total"] == 1
    assert signal["metrics"]["concern_total"] == 2
    payload = json.dumps(result, sort_keys=True).lower()
    for term in ("pass", "fail", "block", "verdict", "must-fix", "patch", "apply"):
        assert term not in payload


def test_code_review_diff_observes_public_api_migration_path(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "api_migrations": [
                        {
                            "api_glob": "src/api/*.py",
                            "new_symbol": "build_project_tree",
                            "from_path": "src/api/__init__.py",
                        }
                    ],
                },
                "plan_fingerprint": "observed-api-migration-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/__init__.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    encoded = json.dumps(result, sort_keys=True)
    assert "planned_public_api_migration_not_observed" not in encoded
    assert "unexpected_changed_file" not in encoded
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["public_api_migration_total"] == 1
    assert signal["metrics"]["observed_public_api_migration_total"] == 1
    assert signal["metrics"]["missing_public_api_migration_total"] == 0
    assert signal["metrics"]["concern_total"] == 0


def test_code_review_diff_empty_diff_reports_missing_public_api_migration(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "public_api_migrations": [{"api_path": "src/api/__init__.py"}],
                },
                "plan_fingerprint": "empty-api-migration-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 0,
            "changed_files": [],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concern = next(item for item in result["concerns"] if item["kind"] == "plan-diff-consistency")
    assert concern["location"]["path"] == "src/api/__init__.py"
    assert "plan_diff_consistency.observation=planned_public_api_migration_not_observed" in concern["evidence"]
    assert "plan_diff_consistency.changed_file_total=0" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["public_api_migration_total"] == 1
    assert signal["metrics"]["observed_public_api_migration_total"] == 0
    assert signal["metrics"]["missing_public_api_migration_total"] == 1
    assert signal["metrics"]["concern_total"] == 1
    payload = json.dumps(result, sort_keys=True).lower()
    for term in ("pass", "fail", "block", "verdict", "must-fix", "patch", "apply"):
        assert term not in payload


def test_code_review_diff_ignores_string_public_api_migrations(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "public_api_migrations": ["update src/api/__init__.py"],
                    "api_migrations": ["rename build_tree"],
                },
                "plan_fingerprint": "string-api-migration-plan",
                "artifacts": {"plan_path": "plans/api.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 0,
            "changed_files": [],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    assert result["concerns"] == []
    assert result["signals"] == []


def test_code_review_diff_adds_missing_semantic_intent_terms_concern(tmp_path, monkeypatch) -> None:
    source = tmp_path / "src" / "api"
    source.mkdir(parents=True)
    (source / "handler.py").write_text(
        "def handle(request):\n    return {'status': 'accepted'}\n",
        encoding="utf-8",
    )
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py"}],
                    "intent_checks": [
                        {
                            "label": "auth boundary",
                            "source_glob": "src/api/**",
                            "required_terms": ["authorize", "audit"],
                        }
                    ],
                },
                "plan_fingerprint": "semantic-missing",
                "artifacts": {"plan_path": "plans/auth.md"},
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concern = next(
        item
        for item in result["concerns"]
        if "plan_diff_consistency.observation=planned_intent_terms_not_observed" in item["evidence"]
    )
    assert concern["kind"] == "plan-diff-consistency"
    assert concern["location"]["path"] == "src/api/handler.py"
    assert "plan_diff_consistency.intent_label=auth boundary" in concern["evidence"]
    assert "plan_diff_consistency.intent_source=src/api/**" in concern["evidence"]
    assert "plan_diff_consistency.required_term_total=2" in concern["evidence"]
    assert "plan_diff_consistency.required_terms=audit,authorize" in concern["evidence"]
    assert "plan_diff_consistency.missing_required_terms=audit,authorize" in concern["evidence"]
    assert "plan_diff_consistency.scoped_changed_file_total=1" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["semantic_intent_total"] == 1
    assert signal["metrics"]["observed_semantic_intent_total"] == 0
    assert signal["metrics"]["missing_semantic_intent_total"] == 1
    assert signal["metrics"]["conflicting_semantic_intent_total"] == 0


def test_code_review_diff_observes_semantic_intent_any_of_terms(tmp_path, monkeypatch) -> None:
    source = tmp_path / "src" / "service"
    source.mkdir(parents=True)
    (source / "model.py").write_text(
        "def update_model(record):\n    return {'migration_status': 'ready'}\n",
        encoding="utf-8",
    )
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/service/model.py"}],
                    "semantic_intents": [
                        {
                            "source": "src/service/**",
                            "any_of_terms": ["migration_status", "migration state"],
                        }
                    ],
                },
                "plan_fingerprint": "semantic-observed",
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/service/model.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    encoded = json.dumps(result, sort_keys=True)
    assert "planned_intent_terms_not_observed" not in encoded
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["semantic_intent_total"] == 1
    assert signal["metrics"]["observed_semantic_intent_total"] == 1
    assert signal["metrics"]["missing_semantic_intent_total"] == 0
    assert signal["metrics"]["conflicting_semantic_intent_total"] == 0


def test_code_review_diff_adds_semantic_intent_conflict_concern(tmp_path, monkeypatch) -> None:
    source = tmp_path / "src" / "api"
    source.mkdir(parents=True)
    (source / "handler.py").write_text(
        "def handle(request):\n    return {'deprecated_mode': True}\n",
        encoding="utf-8",
    )
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py"}],
                    "intent_checks": [
                        {
                            "source": "src/api/**",
                            "must_not_include": ["deprecated_mode"],
                            "reason": "new handler should avoid deprecated mode",
                        }
                    ],
                },
                "plan_fingerprint": "semantic-conflict",
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    concern = next(
        item
        for item in result["concerns"]
        if "plan_diff_consistency.observation=planned_intent_conflict_observed" in item["evidence"]
    )
    assert concern["location"]["path"] == "src/api/handler.py"
    assert "plan_diff_consistency.intent_label=new handler should avoid deprecated mode" in concern["evidence"]
    assert "plan_diff_consistency.forbidden_term_total=1" in concern["evidence"]
    assert "plan_diff_consistency.forbidden_terms=deprecated_mode" in concern["evidence"]
    assert "plan_diff_consistency.observed_forbidden_terms=deprecated_mode" in concern["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["semantic_intent_total"] == 1
    assert signal["metrics"]["conflicting_semantic_intent_total"] == 1


def test_code_review_diff_ignores_string_semantic_intent_entries(tmp_path, monkeypatch) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "intent_checks": ["must include authorization"],
                    "semantic_intents": ["avoid deprecated mode"],
                },
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    assert result["signals"] == []
    assert result["concerns"] == []


def test_code_review_diff_semantic_intent_without_readable_scoped_file_has_metrics_only(
    tmp_path,
    monkeypatch,
) -> None:
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/missing.py"}],
                    "intent_checks": [
                        {
                            "for_path": "src/api/**",
                            "must_include": ["authorize"],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/missing.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    result = code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review)

    assert result["concerns"] == []
    signal = next(item for item in result["signals"] if item["kind"] == "plan_diff_consistency")
    assert signal["metrics"]["semantic_intent_total"] == 1
    assert signal["metrics"]["observed_semantic_intent_total"] == 0
    assert signal["metrics"]["missing_semantic_intent_total"] == 0
    assert signal["metrics"]["conflicting_semantic_intent_total"] == 0


def test_code_review_diff_semantic_intent_output_avoids_execution_and_gate_terms(tmp_path, monkeypatch) -> None:
    source = tmp_path / "src" / "api"
    source.mkdir(parents=True)
    (source / "handler.py").write_text("def handle():\n    return 'current'\n", encoding="utf-8")
    plan_review = tmp_path / "plan-review.json"
    plan_review.write_text(
        json.dumps(
            {
                "mode": "plan_review",
                "understood_plan": {
                    "changes": [{"path": "src/api/handler.py"}],
                    "intent_checks": [{"source": "src/api/**", "all_of": ["authorize"]}],
                },
            }
        ),
        encoding="utf-8",
    )
    report = {
        **_empty_review_report(),
        "change_analysis": {
            "changed_file_total": 1,
            "changed_files": ["src/api/handler.py"],
            "components": [],
        },
    }
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: report)

    payload = json.dumps(code_review.run_code_review_diff(tmp_path, plan_review_path=plan_review), sort_keys=True).lower()

    for term in ("pass", "fail", "block", "verdict", "must-fix", "patch", "apply"):
        assert term not in payload


def test_code_review_since_plan_review_bad_ref_does_not_read_plan(tmp_path, monkeypatch) -> None:
    def raise_bad_ref(*args, **kwargs):
        raise RuntimeError("git range error while running `git diff --numstat missing...HEAD`: fatal: bad revision")

    missing_plan = tmp_path / "missing-plan-review.json"
    monkeypatch.setattr(code_review, "run_analysis", raise_bad_ref)

    result = code_review.run_code_review_since(tmp_path, ref="missing", plan_review_path=missing_plan)

    assert result["review_type"] == "since"
    assert result["concerns"] == []
    assert result["signals"] == []
    assert result["artifacts"] == {}


def test_code_review_since_bad_ref_does_not_run_near_duplicate_detector(tmp_path, monkeypatch) -> None:
    def raise_bad_ref(*args, **kwargs):
        raise RuntimeError("git range error while running `git diff --numstat missing...HEAD`: fatal: bad revision")

    def fail_near_duplicate(*args, **kwargs):
        raise AssertionError("near duplicate detector should not run")

    monkeypatch.setattr(code_review, "run_analysis", raise_bad_ref)
    monkeypatch.setattr(code_review, "near_duplicate_scan", fail_near_duplicate)

    result = code_review.run_code_review_since(tmp_path, ref="missing")

    assert result["review_type"] == "since"
    assert result["concerns"] == []
    assert result["signals"] == []
    assert result["artifacts"] == {}


def test_code_review_full_does_not_run_incremental_contract_or_plan_scanners(tmp_path, monkeypatch) -> None:
    def fail_architecture_contract_scan(*args, **kwargs):
        raise AssertionError("architecture contract scan should not run for full review")

    def fail_plan_diff_scan(*args, **kwargs):
        raise AssertionError("plan diff scan should not run for full review")

    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])
    monkeypatch.setattr(code_review, "architecture_contract_scan", fail_architecture_contract_scan)
    monkeypatch.setattr(code_review, "plan_diff_consistency_scan", fail_plan_diff_scan)

    result = code_review.run_code_review_full(tmp_path)

    assert result["review_type"] == "full"
    assert all(item["kind"] != "architecture_contract" for item in result["signals"])
    assert all(item["kind"] != "plan_diff_consistency" for item in result["signals"])


def test_code_review_full_enriches_concerns_with_external_risk_context(tmp_path, monkeypatch) -> None:
    risk_path = tmp_path / "risk-context.json"
    risk_path.write_text(
        json.dumps(
            {
                "coverage_by_file": {"src/legacy/old_service.py": {"line_rate": 0.42}},
                "churn_by_file": {"src/legacy/old_service.py": {"changes": 13}},
                "complexity_by_file": {
                    "src/legacy/old_service.py": {"cyclomatic": 18.25},
                    "docs/legacy.md": 4,
                    "src/unmatched.py": {"score": 99},
                },
                "public_api_files": {
                    "src/legacy/old_service.py": {"exports": ["OldService"]},
                    "docs/legacy.md": False,
                    "src/unmatched.py": True,
                },
                "historical_recurrence_by_file": {
                    "src/legacy/old_service.py": {"recent_count": 3},
                    "docs/legacy.md": 1,
                },
                "test_files_by_source": {"src/legacy/old_service.py": []},
                "changed_tests": ["tests/test_legacy.py"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    enriched = [
        concern
        for concern in result["concerns"]
        if concern["location"]["path"] == "src/legacy/old_service.py"
        and "risk_context.coverage=0.42" in concern["evidence"]
    ]
    assert enriched
    assert "risk_context.coverage_level=low" in enriched[0]["evidence"]
    assert "risk_context.churn=13" in enriched[0]["evidence"]
    assert "risk_context.churn_level=high" in enriched[0]["evidence"]
    artifact_path = result["artifacts"]["code_review_concerns_json"]
    artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    full_enriched = [
        concern
        for concern in artifact["concerns"]
        if concern["location"]["path"] == "src/legacy/old_service.py"
        and "risk_context.related_test_total=0" in concern["evidence"]
    ]
    assert full_enriched
    assert "risk_context.complexity=18.25" in full_enriched[0]["evidence"]
    assert "risk_context.complexity_level=high" in full_enriched[0]["evidence"]
    assert "risk_context.public_api=true" in full_enriched[0]["evidence"]
    assert "risk_context.recurrence=3" in full_enriched[0]["evidence"]
    assert "risk_context.recurrence_level=recurring" in full_enriched[0]["evidence"]
    doc_enriched = [
        concern
        for concern in artifact["concerns"]
        if concern["location"]["path"] == "docs/legacy.md"
    ]
    assert doc_enriched
    assert "risk_context.complexity=4" in doc_enriched[0]["evidence"]
    assert "risk_context.recurrence=1" in doc_enriched[0]["evidence"]
    assert "risk_context.complexity_level=high" not in doc_enriched[0]["evidence"]
    assert "risk_context.recurrence_level=recurring" not in doc_enriched[0]["evidence"]
    assert "risk_context.public_api=true" not in doc_enriched[0]["evidence"]
    assert all(
        "risk_context." not in fact
        for concern in artifact["concerns"]
        if concern["location"]["path"] != "src/legacy/old_service.py"
        and concern["location"]["path"] != "docs/legacy.md"
        for fact in concern["evidence"]
    )
    signal = next(item for item in result["signals"] if item["kind"] == "risk_context")
    assert signal["summary"] == "3 concerns enriched with external risk context."
    assert signal["metrics"] == {
        "input_file_total": 3,
        "enriched_concern_total": 3,
        "changed_test_total": 1,
        "coverage_file_total": 1,
        "churn_file_total": 1,
        "complexity_file_total": 3,
        "public_api_file_total": 2,
        "recurrence_file_total": 2,
        "test_map_file_total": 1,
        "by_factor": {
            "high_churn": 2,
            "high_complexity": 2,
            "low_coverage": 2,
            "missing_related_tests": 2,
            "public_api": 2,
            "recurring_history": 2,
        },
    }


def test_code_review_risk_context_public_api_files_list_form(tmp_path, monkeypatch) -> None:
    risk_path = tmp_path / "risk-context.json"
    risk_path.write_text(
        json.dumps({"public_api_files": ["docs/legacy.md", "src/unmatched.py"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)
    artifact_path = result["artifacts"]["code_review_concerns_json"]
    artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    doc_concern = next(item for item in artifact["concerns"] if item["location"]["path"] == "docs/legacy.md")

    assert "risk_context.public_api=true" in doc_concern["evidence"]
    assert all(
        "risk_context." not in fact
        for concern in artifact["concerns"]
        if concern["location"]["path"] != "docs/legacy.md"
        for fact in concern["evidence"]
    )
    signal = next(item for item in result["signals"] if item["kind"] == "risk_context")
    assert signal["metrics"]["input_file_total"] == 2
    assert signal["metrics"]["public_api_file_total"] == 2
    assert signal["metrics"]["by_factor"] == {"public_api": 1}


def test_code_review_risk_context_accepts_coverage_py_top_level_files(tmp_path, monkeypatch) -> None:
    risk_path = tmp_path / "coverage.json"
    risk_path.write_text(
        json.dumps(
            {
                "files": {
                    "src/legacy/old_service.py": {
                        "summary": {"percent_covered": 42.5},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    artifact = json.loads(Path(result["artifacts"]["code_review_concerns_json"]).read_text(encoding="utf-8"))
    enriched = [
        concern
        for concern in artifact["concerns"]
        if concern["location"]["path"] == "src/legacy/old_service.py"
        and "risk_context.coverage=0.42" in concern["evidence"]
    ]
    assert enriched
    assert all("risk_context.coverage_level=low" in concern["evidence"] for concern in enriched)
    signal = next(item for item in result["signals"] if item["kind"] == "risk_context")
    assert signal["metrics"]["coverage_file_total"] == 1
    assert signal["metrics"]["by_factor"]["low_coverage"] == 2


def test_code_review_risk_context_nested_coverage_py_explicit_coverage_overrides(
    tmp_path,
    monkeypatch,
) -> None:
    risk_path = tmp_path / "coverage.json"
    risk_path.write_text(
        json.dumps(
            {
                "coverage_py": {
                    "files": {
                        "src/legacy/old_service.py": {
                            "summary": {"percent_covered": 20},
                        }
                    }
                },
                "coverage_by_file": {"src/legacy/old_service.py": {"coverage": 0.85}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    artifact = json.loads(Path(result["artifacts"]["code_review_concerns_json"]).read_text(encoding="utf-8"))
    enriched = [
        concern
        for concern in artifact["concerns"]
        if concern["location"]["path"] == "src/legacy/old_service.py"
    ]
    assert enriched
    assert all("risk_context.coverage=0.85" in concern["evidence"] for concern in enriched)
    assert all("risk_context.coverage=0.20" not in concern["evidence"] for concern in enriched)
    assert all("risk_context.coverage_level=low" not in concern["evidence"] for concern in enriched)


def test_code_review_risk_context_radon_list_complexity_uses_max_block(tmp_path, monkeypatch) -> None:
    risk_path = tmp_path / "radon.json"
    risk_path.write_text(
        json.dumps(
            {
                "radon_cc": {
                    "src/legacy/old_service.py": [
                        {"name": "small", "complexity": 5},
                        {"name": "large", "complexity": 19},
                    ],
                    "docs/legacy.md": {"average_complexity": 4},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    artifact = json.loads(Path(result["artifacts"]["code_review_concerns_json"]).read_text(encoding="utf-8"))
    service = next(
        concern
        for concern in artifact["concerns"]
        if concern["location"]["path"] == "src/legacy/old_service.py"
    )
    doc = next(concern for concern in artifact["concerns"] if concern["location"]["path"] == "docs/legacy.md")
    assert "risk_context.complexity=19" in service["evidence"]
    assert "risk_context.complexity_level=high" in service["evidence"]
    assert "risk_context.complexity=4" in doc["evidence"]
    assert "risk_context.complexity_level=high" not in doc["evidence"]
    signal = next(item for item in result["signals"] if item["kind"] == "risk_context")
    assert signal["metrics"]["complexity_file_total"] == 2
    assert signal["metrics"]["by_factor"]["high_complexity"] == 2


def test_code_review_risk_context_churn_aliases_and_explicit_churn_override(
    tmp_path,
    monkeypatch,
) -> None:
    risk_path = tmp_path / "churn.json"
    risk_path.write_text(
        json.dumps(
            {
                "git_churn_by_file": {"src/legacy/old_service.py": {"count": 4}},
                "churn_report": {"src/legacy/old_service.py": {"changes": 7}},
                "churn_by_file": {"src/legacy/old_service.py": {"churn": 12}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    artifact = json.loads(Path(result["artifacts"]["code_review_concerns_json"]).read_text(encoding="utf-8"))
    enriched = [
        concern
        for concern in artifact["concerns"]
        if concern["location"]["path"] == "src/legacy/old_service.py"
    ]
    assert enriched
    assert all("risk_context.churn=12" in concern["evidence"] for concern in enriched)
    assert all("risk_context.churn=7" not in concern["evidence"] for concern in enriched)
    assert all("risk_context.churn_level=high" in concern["evidence"] for concern in enriched)
    signal = next(item for item in result["signals"] if item["kind"] == "risk_context")
    assert signal["metrics"]["churn_file_total"] == 1
    assert signal["metrics"]["by_factor"]["high_churn"] == 2


def test_code_review_risk_context_ignores_unsupported_report_shapes(tmp_path, monkeypatch) -> None:
    risk_path = tmp_path / "risk.json"
    risk_path.write_text(
        json.dumps(
            {
                "coverage_report": {"files": {"src/legacy/old_service.py": {"summary": {"ignored": "x"}}}},
                "radon_cc": {"src/legacy/old_service.py": [{"rank": "A"}]},
                "churn_report": ["src/legacy/old_service.py"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    artifact = json.loads(Path(result["artifacts"]["code_review_concerns_json"]).read_text(encoding="utf-8"))
    assert all(
        "risk_context." not in fact
        for concern in artifact["concerns"]
        for fact in concern["evidence"]
    )
    signal = next(item for item in result["signals"] if item["kind"] == "risk_context")
    assert signal["metrics"]["input_file_total"] == 0
    assert signal["metrics"]["enriched_concern_total"] == 0
    assert signal["metrics"]["by_factor"] == {}


def test_code_review_risk_context_does_not_create_concerns_by_itself(tmp_path, monkeypatch) -> None:
    risk_path = tmp_path / "risk.json"
    risk_path.write_text(
        json.dumps(
            {
                "files": {
                    "src/only_in_risk.py": {
                        "summary": {"percent_covered": 10},
                    }
                },
                "radon_cc": {"src/only_in_risk.py": [{"complexity": 30}]},
                "git_churn_by_file": {"src/only_in_risk.py": 99},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _empty_review_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path, risk_context_path=risk_path)

    assert result["summary"]["concern_total"] == 0
    assert result["concerns"] == []
    artifact = json.loads(Path(result["artifacts"]["code_review_concerns_json"]).read_text(encoding="utf-8"))
    assert artifact["concerns"] == []
    signal = next(item for item in result["signals"] if item["kind"] == "risk_context")
    assert signal["metrics"]["input_file_total"] == 1
    assert signal["metrics"]["enriched_concern_total"] == 0


def test_code_review_without_risk_context_has_no_risk_signal(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    result = code_review.run_code_review_full(tmp_path)

    assert all(item["kind"] != "risk_context" for item in result["signals"])
    encoded = json.dumps(result["concerns"], sort_keys=True)
    assert "risk_context." not in encoded


def test_code_review_since_bad_ref_does_not_read_risk_context(tmp_path, monkeypatch) -> None:
    def raise_bad_ref(*args, **kwargs):
        raise RuntimeError("git range error while running `git diff --numstat missing...HEAD`: fatal: bad revision")

    missing_risk = tmp_path / "missing-risk.json"
    monkeypatch.setattr(code_review, "run_analysis", raise_bad_ref)

    result = code_review.run_code_review_since(tmp_path, ref="missing", risk_context_path=missing_risk)

    assert result["review_type"] == "since"
    assert result["concerns"] == []
    assert result["signals"] == []


def test_code_review_full_output_avoids_gate_terms(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(code_review, "run_analysis", lambda *args, **kwargs: _analysis_report())
    monkeypatch.setattr(code_review, "near_duplicate_concerns", lambda root: [])

    payload = json.dumps(
        {
            "full": code_review.run_code_review_full(tmp_path),
            "diff": code_review.run_code_review_diff(tmp_path),
            "since": code_review.run_code_review_since(tmp_path, ref="main"),
        },
        sort_keys=True,
    ).lower()

    assert "pass" not in payload
    assert "fail" not in payload
    assert "block" not in payload
    assert "verdict" not in payload
    assert "must-fix" not in payload
