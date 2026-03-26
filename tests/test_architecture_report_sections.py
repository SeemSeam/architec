from __future__ import annotations

from architec.reporting.architecture_report_sections import render_architecture_report_markdown


def test_render_architecture_report_markdown_fallback_sections() -> None:
    markdown = render_architecture_report_markdown(
        generated_at="2026-03-09T00:00:00Z",
        goal="stabilize architecture",
        question="what to fix first?",
        governance={"full": 70.0, "incremental": 88.0, "overall": 75.0},
        hotspots=[
            {
                "rank": 1,
                "path": "a.py",
                "critical": 3,
                "warning": 2,
                "hotspot_score": 22.5,
            }
        ],
        batches=[
            {"priority": "high", "component": "x:y", "focus_files": ["a.py", "b.py"]},
        ],
        descriptors=[],
        llm_doc=None,
    )
    assert "## Top Hotspots" in markdown
    assert "`#1 a.py`" in markdown
    assert "## Refactor Plan" in markdown
    assert "=> focus: a.py, b.py" in markdown
    assert "## Test And Risk Control" in markdown


def test_render_architecture_report_markdown_llm_sections() -> None:
    markdown = render_architecture_report_markdown(
        generated_at="2026-03-09T00:00:00Z",
        goal="stabilize architecture",
        question="what to fix first?",
        governance={"full": 70.0, "incremental": 88.0, "overall": 75.0},
        hotspots=[],
        batches=[],
        descriptors=[{"component": "a:b", "layer_role": "domain", "confidence": 0.9, "responsibility_summary": "owns B"}],
        llm_doc={
            "title": "Architecture Report - LLM",
            "executive_summary": "summary",
            "score_summary": ["item-1"],
            "top_hotspots": [{"path": "x.py", "risk": "high", "reason": "complex"}],
            "refactor_plan": [{"priority": "P0", "objective": "split file", "focus_files": ["x.py"], "acceptance": "tests pass"}],
            "test_and_risk_control": ["run tests"],
            "next_iteration": "continue",
        },
    )
    assert "# Architecture Report - LLM" in markdown
    assert "## Score Insights" in markdown
    assert "`x.py` | risk: `high` | complex" in markdown
    assert "`P0` split file" in markdown
    assert "## Next Iteration" in markdown

