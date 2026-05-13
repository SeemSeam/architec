from __future__ import annotations

import copy
import json

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
    assert result["summary"]["headline"] == "No new architecture concerns were identified in this diff."
    assert result["summary"]["concern_total"] == 0
    assert result["summary"]["top_concern_total"] == 0
    assert result["summary"]["concern_limit"] == 5
    assert result["concerns"] == []
    assert result["findings"] == []


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
    assert result["summary"]["headline"] == "No new architecture concerns were identified since main."
    assert result["summary"]["concern_total"] == 0
    assert result["summary"]["top_concern_total"] == 0
    assert result["summary"]["concern_limit"] == 5
    assert result["concerns"] == []
    assert result["findings"] == []


def test_run_code_review_since_unresolved_ref_degrades_to_result(tmp_path, monkeypatch) -> None:
    def raise_bad_ref(*args, **kwargs):
        raise RuntimeError("fatal: bad revision 'missing-ref...HEAD'")

    monkeypatch.setattr(code_review, "run_analysis", raise_bad_ref)

    result = code_review.run_code_review_since(tmp_path, ref="missing-ref")

    assert result["mode"] == "code_review"
    assert result["review_type"] == "since"
    assert result["summary"]["headline"] == "Unable to analyze changes since missing-ref."
    assert result["summary"]["reason"] == "The requested since range could not be resolved."
    assert result["summary"]["concern_total"] == 0
    assert result["summary"]["top_concern_total"] == 0
    assert result["summary"]["concern_limit"] == 5
    assert result["concerns"] == []
    assert result["findings"] == []
    assert result["artifacts"] == {}


def test_run_code_review_since_git_range_error_degrades_to_result(tmp_path, monkeypatch) -> None:
    def raise_git_range_error(*args, **kwargs):
        raise RuntimeError("git range error while running `git diff --numstat missing...HEAD`: fatal: bad revision")

    monkeypatch.setattr(code_review, "run_analysis", raise_git_range_error)

    result = code_review.run_code_review_since(tmp_path, ref="missing")

    assert result["mode"] == "code_review"
    assert result["review_type"] == "since"
    assert result["summary"]["headline"] == "Unable to analyze changes since missing."
    assert result["summary"]["reason"] == "The requested since range could not be resolved."
    assert result["concerns"] == []
    assert result["findings"] == []


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
        "near_duplicate_concerns",
        lambda root: [
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
    assert signal["metrics"] == {
        "concern_total": 1,
        "scoped_to_changed_files": True,
        "changed_file_total": 1,
        "candidate_total_before_scope": 1,
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
