from __future__ import annotations

import json

import architec
import architec.baseline as baseline_pkg
from architec.baseline.report import build_baseline_snapshot, write_baseline_artifacts


def _analysis_report(tmp_path) -> dict[str, object]:
    return {
        "meta": {
            "generated_at": "2026-04-03T00:00:00+00:00",
            "path": str(tmp_path),
            "mode": "full",
            "goal": "",
        },
        "scores": {
            "overall": 84.5,
            "governance_overall": 80.0,
            "structure": 89.0,
            "full": 80.0,
            "incremental": None,
            "structure_dimensions": {
                "file_modularity": 70.0,
            },
        },
        "cleanup": {
            "candidate_total": 2,
            "review_required_total": 2,
            "by_kind": {"doc": 1, "source": 1},
            "by_category": {"legacy_impl": 1, "stale_doc": 1},
            "top_candidates": [
                {
                    "path": "docs/legacy.md",
                    "kind": "doc",
                    "category": "stale_doc",
                    "confidence": 0.73,
                    "evidence": ["content:legacy"],
                }
            ],
        },
        "hotspots": [
            {
                "path": "src/core/service.py",
                "component": "core",
                "structure_impact": "cyclomatic_complexity",
            }
        ],
        "components": [
            {
                "component": "core",
                "risk_score": 12.5,
                "critical": 1,
                "warning": 3,
                "labels": ["critical_findings"],
            }
        ],
        "topology": {
            "source_root": "src",
            "needs_folder_management": False,
            "flat_file_total": 1,
            "subpackage_total": 2,
            "flatness_score": 100.0,
            "migration_plan": {
                "summary": "Move 0 files into 0 folders, keep 1 root facades, review 0 uncertain files.",
            },
        },
        "feature_analysis": {
            "retire_plan": {
                "add": [{"component": "core"}],
                "retire": [{"path": "src/legacy/core.py"}],
                "validation": [{"check": "ownership"}],
            }
        },
        "change_analysis": {
            "retire_plan": {
                "add": [],
                "retire": [{"path": "docs/legacy.md"}],
                "validation": [{"check": "verification"}],
            }
        },
        "artifacts": {
            "analysis_json": str(tmp_path / ".architec" / "architec-analysis.json"),
            "summary_md": str(tmp_path / ".architec" / "architec-summary.md"),
        },
    }


def test_baseline_wrapper_exports_are_retired() -> None:
    assert "run_baseline" not in architec.__all__
    assert "run_baseline" not in baseline_pkg.__all__
    assert not hasattr(architec, "run_baseline")
    assert not hasattr(baseline_pkg, "run_baseline")


def test_build_baseline_snapshot_preserves_legacy_snapshot_fields(tmp_path) -> None:
    baseline = build_baseline_snapshot(_analysis_report(tmp_path))

    assert baseline["meta"]["mode"] == "baseline"
    assert baseline["scores"]["overall"] == 84.5
    assert baseline["cleanup"]["candidate_total"] == 2
    assert baseline["retire_plan"]["goal"]["retire_total"] == 1
    assert baseline["source_artifacts"]["analysis_json"].endswith("architec-analysis.json")


def test_write_baseline_artifacts_emits_legacy_snapshot_files(tmp_path) -> None:
    baseline = build_baseline_snapshot(_analysis_report(tmp_path))

    artifacts = write_baseline_artifacts(tmp_path, baseline)

    baseline_path = tmp_path / ".architec" / "architec-baseline.json"
    summary_path = tmp_path / ".architec" / "architec-baseline-summary.md"
    assert artifacts["baseline_json"] == str(baseline_path)
    assert artifacts["baseline_summary_md"] == str(summary_path)
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert payload["meta"]["mode"] == "baseline"
    assert "# Architec Baseline" in summary_path.read_text(encoding="utf-8")
