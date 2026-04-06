from __future__ import annotations

from architec.analysis.analysis_runner_flow import structure_dimensions


def test_structure_dimensions_use_grace_before_penalty() -> None:
    history = {
        "summary": {
            "by_metric": {
                "module_lines": 10,
                "cyclomatic_complexity": 32,
                "line_length_soft_hits": 55,
                "line_length_hard_hits": 16,
            },
            "by_dimension": {},
            "by_severity": {"critical": 6},
        }
    }

    dimensions = structure_dimensions(history)

    assert dimensions["file_modularity"] == 100.0
    assert dimensions["maintainability"] == 100.0


def test_structure_dimensions_penalize_excess_over_grace() -> None:
    history = {
        "summary": {
            "by_metric": {
                "module_lines": 20,
                "cyclomatic_complexity": 52,
                "line_length_soft_hits": 72,
                "line_length_hard_hits": 29,
            },
            "by_dimension": {},
            "by_severity": {"critical": 15},
        }
    }

    dimensions = structure_dimensions(history)

    assert dimensions["file_modularity"] == 86.0
    assert dimensions["maintainability"] == 82.17


def test_structure_dimensions_do_not_penalize_true_compat_wrappers() -> None:
    history = {"summary": {"by_metric": {}, "by_dimension": {}, "by_severity": {}}}

    dimensions = structure_dimensions(
        history,
        topology={
            "flat_file_total": 4,
            "subpackage_total": 6,
            "compat_wrapper_total": 3,
            "needs_folder_management": False,
            "root_placement_review": {
                "misplaced_root_files": [],
                "review_root_files": [],
                "allowed_root_files": ["cli.py", "analysis_runner.py"],
            },
        },
    )

    assert dimensions["package_topology"] == 100.0


def test_structure_dimensions_include_governance_inputs() -> None:
    history = {"summary": {"by_metric": {}, "by_dimension": {}, "by_severity": {}}}

    dimensions = structure_dimensions(
        history,
        topology={
            "flat_file_total": 4,
            "subpackage_total": 6,
            "compat_wrapper_total": 0,
            "needs_folder_management": False,
            "root_placement_review": {
                "misplaced_root_files": [],
                "review_root_files": [],
                "allowed_root_files": ["cli.py"],
            },
        },
        hotspot_digest={
            "items": [
                {
                    "path": "src/core/hotspot.py",
                    "critical": 2,
                    "warning": 3,
                    "hotspot_score": 11.0,
                    "component_score": 52.0,
                }
            ]
        },
        components=[
            {
                "component": "core",
                "risk_score": 8.0,
                "critical": 1,
                "warning": 2,
                "file_count": 7,
            }
        ],
        cleanup={
            "candidate_total": 2,
            "review_required_total": 2,
            "owner_total": 1,
            "ttl_total": 1,
            "expires_total": 1,
            "expired_total": 1,
            "by_category": {"legacy_impl": 1, "stale_doc": 1},
        },
        archive_candidates={
            "candidate_total": 2,
            "ready_total": 1,
            "review_total": 1,
        },
        semantic_judge={
            "status": "ok",
            "candidate_pool_total": 2,
            "reviewed_total": 2,
            "by_decision": {"archive_first": 1, "retire_now": 1},
        },
    )

    assert dimensions["package_topology"] == 100.0
    assert dimensions["hotspot_hygiene"] < 70.0
    assert dimensions["component_balance"] < 80.0
    assert dimensions["cleanup_hygiene"] < 90.0
    assert dimensions["archive_readiness"] > 75.0
    assert dimensions["semantic_alignment"] > 95.0
