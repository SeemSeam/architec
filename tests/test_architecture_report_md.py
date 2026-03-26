from __future__ import annotations

from pathlib import Path

import architec.reporting.architecture_report_md as report_md


def test_write_architecture_report_markdown_fallback(tmp_path: Path) -> None:
    out = report_md.write_architecture_report_markdown(
        tmp_path,
        goal="improve architecture quality",
        question="what to fix first",
        governance={"full": 60.0, "incremental": 42.0, "overall": 53.0},
        hotspot_digest={
            "items": [
                {
                    "rank": 1,
                    "path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
                    "component": "llm-proxy:ops/context",
                    "critical": 10,
                    "warning": 8,
                    "hotspot_score": 88.0,
                }
            ]
        },
        batches=[
            {
                "batch": "B1",
                "component": "llm-proxy:ops/context",
                "priority": "high",
                "focus_files": ["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"],
            }
        ],
        feature={"target_components": []},
        qa={"component": "llm-proxy:ops/context"},
        llm_enabled=False,
    )

    path = Path(out["path"])
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "# Architecture Report" in content
    assert "## Top Hotspots" in content
    assert "## Component Context" in content
    assert "llm-proxy:ops/context" in content
    assert "lifecycle.py" in content
    assert out["llm_used"] is False


def test_write_architecture_report_markdown_with_llm(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    def _fake_complete_json(*args, **kwargs):
        calls["count"] += 1
        return {
            "title": "Architecture Report - Full",
            "executive_summary": "Focus on macro boundaries first.",
            "score_summary": ["Overall remains blocked due to core hotspots."],
            "top_hotspots": [
                {
                    "path": "architec/src/architec/improvement_loop.py",
                    "risk": "high",
                    "reason": "Centralized branching is too dense.",
                }
            ],
            "refactor_plan": [
                {
                    "priority": "P0",
                    "objective": "Split orchestrator responsibilities.",
                    "focus_files": ["architec/src/architec/improvement_loop.py"],
                    "acceptance": "No critical findings increase on touched files.",
                }
            ],
            "test_and_risk_control": ["Run targeted pytest after each structural step."],
            "next_iteration": "Re-evaluate component scores after split.",
            "_llm_model": "glm-5",
            "_llm_provider": "glm:direct",
        }

    monkeypatch.setattr(report_md, "complete_json", _fake_complete_json)

    out = report_md.write_architecture_report_markdown(
        tmp_path,
        goal="improve architecture quality",
        question="what to fix first",
        governance={"full": 60.0, "incremental": 42.0, "overall": 53.0},
        hotspot_digest={"items": []},
        batches=[],
        feature={"target_components": []},
        qa={"component": "architec:src"},
        llm_enabled=True,
    )

    content = Path(out["path"]).read_text(encoding="utf-8")
    assert "# Architecture Report - Full" in content
    assert "Focus on macro boundaries first." in content
    assert out["llm_used"] is True
    assert out["llm_cache_hit"] is False
    assert out["llm_model"] == "glm-5"

    second = report_md.write_architecture_report_markdown(
        tmp_path,
        goal="improve architecture quality",
        question="what to fix first",
        governance={"full": 60.0, "incremental": 42.0, "overall": 53.0},
        hotspot_digest={"items": []},
        batches=[],
        feature={"target_components": []},
        qa={"component": "architec:src"},
        llm_enabled=True,
    )
    assert second["llm_cache_hit"] is True
    assert calls["count"] == 1
