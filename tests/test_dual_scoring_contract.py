from __future__ import annotations

import json
from pathlib import Path

import architec.scoring.component_scoring as component_scoring
from architec.scoring.component_scoring import score_changed_components
from architec.analysis.history_analyzer import analyze_history_and_iterate


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _prepare_hippo_artifacts(root: Path) -> None:
    hippo = root / ".hippocampus"
    _write_json(
        hippo / "architect-metrics.json",
        {
            "scores": {"overall": 7.5},
            "findings": [
                {
                    "path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
                    "severity": "critical",
                    "dimension": "complexity",
                    "metric": "cyclomatic_complexity",
                    "symbol": "ContextLifecycleManager.run",
                    "value": 16,
                    "threshold": 12,
                    "message": "too complex",
                },
                {
                    "path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
                    "severity": "warning",
                    "dimension": "file_size",
                    "metric": "module_lines",
                    "symbol": "",
                    "value": 600,
                    "threshold": 450,
                    "message": "module too large",
                },
            ],
        },
    )
    _write_json(
        hippo / "hippocampus-index.json",
        {
            "files": {
                "llm-proxy/src/llm_proxy/ops/context/lifecycle.py": {
                    "signatures": [
                        {"name": "ContextLifecycleManager", "line": 1, "parent": ""}
                    ]
                }
            },
            "function_dependencies": {},
        },
    )
    _write_json(
        hippo / "code-signatures.json",
        {
            "files": {
                "llm-proxy/src/llm_proxy/ops/context/lifecycle.py": {
                    "signatures": [
                        {"name": "ContextLifecycleManager.run", "line": 10, "parent": ""}
                    ]
                }
            }
        },
    )
    (hippo / "structure-prompt.md").write_text("test", encoding="utf-8")


def test_history_report_contains_full_score(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _prepare_hippo_artifacts(root)

    report = analyze_history_and_iterate(root, llm_enabled=False)
    assert "full_score" in report
    assert report["full_score"]["mode"] == "full"
    assert report["full_score"]["recommendation"] in {"approve", "needs_changes", "block"}
    assert report["descriptor_count"] > 0
    assert report["component_debt"][0]["component"] == "llm-proxy:ops/context"


def test_component_report_contains_incremental_score(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    _prepare_hippo_artifacts(root)

    monkeypatch.setattr(
        component_scoring,
        "_changed_files",
        lambda *_args, **_kwargs: [
            {
                "path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
                "added": 30,
                "deleted": 8,
            }
        ],
    )

    report = score_changed_components(root, llm_enabled=False)
    assert "incremental_score" in report
    assert report["incremental_score"]["mode"] == "incremental"
    assert report["incremental_score"]["recommendation"] in {
        "approve",
        "needs_changes",
        "block",
    }
    assert "runtime" in report
    assert "changed_files" in report["runtime"]["timings"]
    assert "total_elapsed_sec" in report["runtime"]
    assert report["components"][0]["descriptor"]["layer_role"] == "orchestration"
    assert report["components"][0]["descriptor"]["confidence"] > 0.0


def test_component_scoring_respects_changed_file_scope_env(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "repo"
    _prepare_hippo_artifacts(root)

    # Force git diff fallback path to be noisy; env scope should override this.
    monkeypatch.setattr(
        component_scoring,
        "_changed_files",
        lambda *_args, **_kwargs: [
            {"path": "architec/README.md", "added": 999, "deleted": 0}
        ],
    )
    monkeypatch.setenv(
        "ARCH_SCORE_CHANGED_FILES",
        json.dumps(["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"]),
    )

    # Call the internal helper that reads env scope to avoid monkeypatched _changed_files.
    scoped = component_scoring._changed_files_from_env_scope()
    assert scoped == [
        {
            "path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
            "added": 0,
            "deleted": 0,
        }
    ]
