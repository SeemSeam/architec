from __future__ import annotations

from typing import Any


def _llm_list(llm_doc: dict[str, Any] | None, key: str) -> list[Any]:
    value = (llm_doc or {}).get(key, [])
    return value if isinstance(value, list) else []


def _render_score_insights(lines: list[str], llm_doc: dict[str, Any] | None) -> None:
    score_summary = _llm_list(llm_doc, "score_summary")
    if not score_summary:
        return
    lines.append("## Score Insights")
    for item in score_summary[:8]:
        lines.append(f"- {str(item)}")
    lines.append("")


def _render_hotspots(
    lines: list[str],
    *,
    llm_doc: dict[str, Any] | None,
    hotspots: list[dict[str, Any]],
) -> None:
    lines.append("## Top Hotspots")
    llm_hotspots = _llm_list(llm_doc, "top_hotspots")
    if llm_hotspots:
        for item in llm_hotspots[:10]:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "") or "")
            risk = str(item.get("risk", "") or "")
            reason = str(item.get("reason", "") or "")
            lines.append(f"- `{path}` | risk: `{risk}` | {reason}")
    else:
        for item in hotspots[:10]:
            lines.append(
                f"- `#{item.get('rank', 0)} {item.get('path', '')}` "
                f"(critical={item.get('critical', 0)}, warning={item.get('warning', 0)}, score={item.get('hotspot_score', 0.0)})"
            )
    lines.append("")


def _render_component_context(lines: list[str], descriptors: list[dict[str, Any]]) -> None:
    if not descriptors:
        return
    lines.append("## Component Context")
    for item in descriptors[:8]:
        if not isinstance(item, dict):
            continue
        component = str(item.get("component", "") or "")
        layer_role = str(item.get("layer_role", "") or "")
        confidence = float(item.get("confidence", 0.0) or 0.0)
        summary = str(item.get("responsibility_summary", "") or "")
        neighbors = item.get("dependency_neighbors", [])
        if not isinstance(neighbors, list):
            neighbors = []
        lines.append(
            f"- `{component}` | layer=`{layer_role}` | confidence=`{confidence}` | {summary}"
        )
        if neighbors:
            lines.append(f"  neighbors: {', '.join(str(x) for x in neighbors[:4])}")
    lines.append("")


def _render_refactor_plan(
    lines: list[str],
    *,
    llm_doc: dict[str, Any] | None,
    batches: list[dict[str, Any]],
) -> None:
    lines.append("## Refactor Plan")
    llm_plan = _llm_list(llm_doc, "refactor_plan")
    if llm_plan:
        for item in llm_plan[:12]:
            if not isinstance(item, dict):
                continue
            prio = str(item.get("priority", "P1") or "P1")
            objective = str(item.get("objective", "") or "")
            files = item.get("focus_files", [])
            if not isinstance(files, list):
                files = []
            acceptance = str(item.get("acceptance", "") or "")
            lines.append(f"- `{prio}` {objective}")
            if files:
                lines.append(f"  files: {', '.join(str(x) for x in files[:6])}")
            if acceptance:
                lines.append(f"  acceptance: {acceptance}")
    else:
        for item in batches[:8]:
            lines.append(
                f"- `{item.get('priority', 'medium')}` {item.get('component', '')} "
                f"=> focus: {', '.join(str(x) for x in item.get('focus_files', [])[:4])}"
            )
    lines.append("")


def _render_test_and_risk_control(lines: list[str], llm_doc: dict[str, Any] | None) -> None:
    lines.append("## Test And Risk Control")
    controls = _llm_list(llm_doc, "test_and_risk_control")
    if controls:
        for item in controls[:10]:
            lines.append(f"- {str(item)}")
    else:
        lines.append("- Run targeted pytest suites on touched components before each merge.")
        lines.append("- Require no new critical findings on touched files.")
        lines.append("- Use behavior-preserving refactor first, then optimize structure.")
    lines.append("")


def render_architecture_report_markdown(
    *,
    generated_at: str,
    goal: str,
    question: str,
    governance: dict[str, Any],
    hotspots: list[dict[str, Any]],
    batches: list[dict[str, Any]],
    descriptors: list[dict[str, Any]],
    llm_doc: dict[str, Any] | None,
) -> str:
    title = str((llm_doc or {}).get("title", "Architecture Report") or "Architecture Report")
    summary = str((llm_doc or {}).get("executive_summary", "") or "")
    if not summary:
        summary = "This report summarizes architecture risks, hotspot priorities, and actionable refactor steps."

    lines: list[str] = [
        f"# {title}",
        "",
        f"- Generated At: `{generated_at}`",
        f"- Goal: `{goal}`",
        f"- Question: `{question}`",
        "",
        "## Executive Summary",
        summary,
        "",
        "## Governance Scores",
        f"- Full: `{governance.get('full', 0.0)}`",
        f"- Incremental: `{governance.get('incremental', 0.0)}`",
        f"- Overall: `{governance.get('overall', 0.0)}`",
        "",
    ]

    _render_score_insights(lines, llm_doc)
    _render_hotspots(lines, llm_doc=llm_doc, hotspots=hotspots)
    _render_component_context(lines, descriptors)
    _render_refactor_plan(lines, llm_doc=llm_doc, batches=batches)
    _render_test_and_risk_control(lines, llm_doc)

    next_iter = str((llm_doc or {}).get("next_iteration", "") or "")
    if next_iter:
        lines.append("## Next Iteration")
        lines.append(next_iter)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"

