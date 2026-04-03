from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.integration.paths import BASELINE_JSON_PATH, BASELINE_SUMMARY_MD_PATH
from architec.support.io_utils import utc_now_iso, write_json


def _report_section(report: dict[str, Any], key: str, expected_type: type) -> Any:
    value = report.get(key, expected_type())
    return value if isinstance(value, expected_type) else expected_type()


def _retire_plan_counts(analysis: dict[str, Any]) -> dict[str, int]:
    retire_plan = (
        analysis.get("retire_plan", {})
        if isinstance(analysis.get("retire_plan"), dict)
        else {}
    )
    add_items = retire_plan.get("add", []) if isinstance(retire_plan.get("add"), list) else []
    retire_items = retire_plan.get("retire", []) if isinstance(retire_plan.get("retire"), list) else []
    validations = (
        retire_plan.get("validation", [])
        if isinstance(retire_plan.get("validation"), list)
        else []
    )
    return {
        "add_total": len(add_items),
        "retire_total": len(retire_items),
        "validation_total": len(validations),
    }


def build_baseline_snapshot(report: dict[str, Any]) -> dict[str, Any]:
    meta = _report_section(report, "meta", dict)
    scores = _report_section(report, "scores", dict)
    cleanup = _report_section(report, "cleanup", dict)
    hotspots = _report_section(report, "hotspots", list)
    components = _report_section(report, "components", list)
    topology = _report_section(report, "topology", dict)
    feature = _report_section(report, "feature_analysis", dict)
    change = _report_section(report, "change_analysis", dict)
    artifacts = _report_section(report, "artifacts", dict)

    migration = (
        topology.get("migration_plan", {})
        if isinstance(topology.get("migration_plan"), dict)
        else {}
    )
    return {
        "meta": {
            "generated_at": utc_now_iso(),
            "path": str(meta.get("path", "") or ""),
            "mode": "baseline",
            "source_mode": str(meta.get("mode", "") or ""),
            "source_generated_at": str(meta.get("generated_at", "") or ""),
            "goal": str(meta.get("goal", "") or ""),
        },
        "scores": {
            "overall": scores.get("overall"),
            "governance_overall": scores.get("governance_overall"),
            "structure": scores.get("structure"),
            "full": scores.get("full"),
            "incremental": scores.get("incremental"),
            "structure_dimensions": scores.get("structure_dimensions", {}),
        },
        "cleanup": {
            "candidate_total": int(cleanup.get("candidate_total", 0) or 0),
            "review_required_total": int(cleanup.get("review_required_total", 0) or 0),
            "owner_total": int(cleanup.get("owner_total", 0) or 0),
            "ttl_total": int(cleanup.get("ttl_total", 0) or 0),
            "expires_total": int(cleanup.get("expires_total", 0) or 0),
            "expired_total": int(cleanup.get("expired_total", 0) or 0),
            "by_kind": dict(cleanup.get("by_kind", {}))
            if isinstance(cleanup.get("by_kind"), dict)
            else {},
            "by_category": dict(cleanup.get("by_category", {}))
            if isinstance(cleanup.get("by_category"), dict)
            else {},
            "by_owner": dict(cleanup.get("by_owner", {}))
            if isinstance(cleanup.get("by_owner"), dict)
            else {},
            "top_candidates": [
                item for item in cleanup.get("top_candidates", [])[:10]
                if isinstance(item, dict)
            ]
            if isinstance(cleanup.get("top_candidates"), list)
            else [],
        },
        "hotspots": [item for item in hotspots[:10] if isinstance(item, dict)],
        "components": [item for item in components[:10] if isinstance(item, dict)],
        "topology": {
            "source_root": str(topology.get("source_root", "") or ""),
            "needs_folder_management": bool(topology.get("needs_folder_management", False)),
            "flat_file_total": int(topology.get("flat_file_total", 0) or 0),
            "subpackage_total": int(topology.get("subpackage_total", 0) or 0),
            "flatness_score": topology.get("flatness_score"),
            "migration_summary": str(migration.get("summary", "") or ""),
        },
        "retire_plan": {
            "goal": _retire_plan_counts(feature),
            "diff": _retire_plan_counts(change),
        },
        "source_artifacts": {
            key: str(value or "")
            for key, value in artifacts.items()
            if isinstance(key, str)
        },
    }


def render_baseline_summary(snapshot: dict[str, Any]) -> str:
    meta = _report_section(snapshot, "meta", dict)
    scores = _report_section(snapshot, "scores", dict)
    cleanup = _report_section(snapshot, "cleanup", dict)
    hotspots = _report_section(snapshot, "hotspots", list)
    components = _report_section(snapshot, "components", list)
    topology = _report_section(snapshot, "topology", dict)
    retire_plan = _report_section(snapshot, "retire_plan", dict)

    lines = [
        "# Architec Baseline",
        "",
        f"- Generated At: `{meta.get('generated_at', '')}`",
        f"- Path: `{meta.get('path', '')}`",
        f"- Source Mode: `{meta.get('source_mode', '')}`",
        f"- Source Generated At: `{meta.get('source_generated_at', '')}`",
        "",
        "## Score Snapshot",
        f"- Overall: `{scores.get('overall', 0.0)}`",
        f"- Governance Overall: `{scores.get('governance_overall', 0.0)}`",
        f"- Structure: `{scores.get('structure', 0.0)}`",
        f"- Full: `{scores.get('full', 0.0)}`",
    ]
    if scores.get("incremental") is not None:
        lines.append(f"- Incremental: `{scores.get('incremental', 0.0)}`")

    lines.extend(
        [
            "",
            "## Cleanup Baseline",
            f"- Candidate Total: `{cleanup.get('candidate_total', 0)}`",
            f"- Review Required: `{cleanup.get('review_required_total', 0)}`",
        ]
    )
    owner_total = int(cleanup.get("owner_total", 0) or 0)
    ttl_total = int(cleanup.get("ttl_total", 0) or 0)
    expires_total = int(cleanup.get("expires_total", 0) or 0)
    expired_total = int(cleanup.get("expired_total", 0) or 0)
    if owner_total or ttl_total or expires_total or expired_total:
        lines.append(
            f"- Metadata: owner=`{owner_total}` | ttl=`{ttl_total}` | "
            f"expires_at=`{expires_total}` | expired=`{expired_total}`"
        )
    by_category = cleanup.get("by_category", {})
    if isinstance(by_category, dict) and by_category:
        rendered = ", ".join(f"{key}={value}" for key, value in by_category.items())
        lines.append(f"- Categories: {rendered}")

    lines.extend(["", "## Hotspot Baseline"])
    added_hotspot = False
    for item in hotspots[:5]:
        if not isinstance(item, dict):
            continue
        added_hotspot = True
        lines.append(
            f"- `{item.get('path', '')}` | component=`{item.get('component', '')}` | "
            f"impact=`{item.get('structure_impact', '')}`"
        )
    if not added_hotspot:
        lines.append("- No hotspots recorded.")

    lines.extend(["", "## Component Baseline"])
    added_component = False
    for item in components[:5]:
        if not isinstance(item, dict):
            continue
        added_component = True
        lines.append(
            f"- `{item.get('component', '')}` | risk=`{item.get('risk_score', 0.0)}` | "
            f"critical=`{item.get('critical', 0)}` | warning=`{item.get('warning', 0)}`"
        )
    if not added_component:
        lines.append("- No component risk entries recorded.")

    lines.extend(
        [
            "",
            "## Topology Baseline",
            f"- Source Root: `{topology.get('source_root', '')}`",
            f"- Needs Folder Management: `{topology.get('needs_folder_management', False)}`",
            f"- Migration Summary: {topology.get('migration_summary', '') or 'none'}",
            "",
            "## Retire Plan Baseline",
        ]
    )
    goal = retire_plan.get("goal", {}) if isinstance(retire_plan.get("goal"), dict) else {}
    diff = retire_plan.get("diff", {}) if isinstance(retire_plan.get("diff"), dict) else {}
    lines.append(
        f"- Goal Retire Plan: adds=`{goal.get('add_total', 0)}` | retires=`{goal.get('retire_total', 0)}` | "
        f"validations=`{goal.get('validation_total', 0)}`"
    )
    lines.append(
        f"- Diff Retire Plan: adds=`{diff.get('add_total', 0)}` | retires=`{diff.get('retire_total', 0)}` | "
        f"validations=`{diff.get('validation_total', 0)}`"
    )
    return "\n".join(lines).rstrip() + "\n"


def write_baseline_artifacts(root: Path, snapshot: dict[str, Any]) -> dict[str, str]:
    baseline_path = root / BASELINE_JSON_PATH
    summary_path = root / BASELINE_SUMMARY_MD_PATH
    write_json(baseline_path, snapshot)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_baseline_summary(snapshot), encoding="utf-8")
    return {
        "baseline_json": str(baseline_path),
        "baseline_summary_md": str(summary_path),
    }


__all__ = [
    "build_baseline_snapshot",
    "render_baseline_summary",
    "write_baseline_artifacts",
]
