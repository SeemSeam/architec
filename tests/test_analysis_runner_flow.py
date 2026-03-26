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
