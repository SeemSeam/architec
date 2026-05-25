from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from architec.analysis.analysis_runner_llm import llm_summary as incremental_llm_summary
from architec.analysis.public import run_analysis
from architec.code_review.architecture_contracts import architecture_contract_scan
from architec.code_review.near_duplicate import near_duplicate_concerns, near_duplicate_scan
from architec.code_review.plan_diff_consistency import load_plan_review, plan_diff_consistency_scan
from architec.code_review.risk_context import (
    apply_risk_context,
    load_risk_context,
    risk_context_reinforcement_factors,
)
from architec.code_review.shadow_implementation import (
    shadow_implementation_file_dry_run,
    shadow_implementation_scan,
)
from architec.events.public import append_review_event
from architec.integration.bundle_loader import REQUIRED_BUNDLE_FILES
from architec.scoring.component_scoring_git import changed_files as git_changed_files
from architec.support.io_utils import ProgressFn, clamp, read_json, write_json


CONCERN_LIMIT = 5
CONCERN_KIND_SOFT_CAP = 2
CONCERN_EVIDENCE_LIMIT = 8
CONCERN_BLAST_RADIUS_LIMIT = 8
CONCERN_REFERENCES_LIMIT = 3
SIGNAL_METRIC_DICT_LIMIT = 12
CONCERNS_ARTIFACT_FILE = "code-review-concerns.json"
DISCOVERY_ARTIFACT_FILE = "code-review-discovery.json"
INCREMENTAL_SELECTED_SCOPE_KINDS = {"architecture-contract", "plan-diff-consistency"}
SMALL_FLAT_TOPOLOGY_FILE_LIMIT = 10
SEMANTIC_REVIEW_CONFIDENCE_FLOOR = 0.76
SEMANTIC_ARCHIVE_FIRST_CONFIDENCE_FLOOR = 0.8
SEMANTIC_RETIRE_NOW_CONFIDENCE_FLOOR = 0.86
PROMOTABLE_DISCOVERY_REASONS = {
    "thin_wrapper_different_target",
    "variant_family_thin_wrapper_different_target",
}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_confidence(value: object, default: float) -> float:
    try:
        return round(clamp(float(value), 0.0, 1.0), 2)
    except (TypeError, ValueError):
        return round(clamp(default, 0.0, 1.0), 2)


def _location(path: str) -> dict[str, Any]:
    return {
        "path": path,
        "line": 0,
        "symbol": "",
        "symbol_kind": "module",
    }


def _stable_concern_id(
    kind: str,
    *,
    source: str,
    location: dict[str, Any],
    evidence: list[str],
) -> str:
    payload = {
        "kind": kind,
        "source": source,
        "location": {
            "path": str(location.get("path", "") or ""),
            "line": int(location.get("line", 0) or 0),
            "symbol": str(location.get("symbol", "") or ""),
            "symbol_kind": str(location.get("symbol_kind", "") or ""),
        },
        "evidence": sorted(str(item) for item in evidence),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:{kind}:{digest}"


def _cleanup_concerns(report: dict[str, Any]) -> list[dict[str, Any]]:
    cleanup = _dict(report.get("cleanup"))
    candidates = _list(cleanup.get("top_candidates"))
    concerns: list[dict[str, Any]] = []
    for item in candidates[:5]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "").strip()
        if not path:
            continue
        category = str(item.get("category", "") or "cleanup").strip()
        kind = str(item.get("kind", "") or "").strip()
        raw_evidence = item.get("evidence", [])
        evidence = [str(part) for part in raw_evidence[:4]] if isinstance(raw_evidence, list) else []
        if kind:
            evidence.insert(0, f"cleanup.kind={kind}")
        if category:
            evidence.insert(0, f"cleanup.category={category}")
        location = _location(path)
        concerns.append(
            {
                "concern_id": _stable_concern_id(
                    "cleanup",
                    source="cleanup",
                    location=location,
                    evidence=evidence,
                ),
                "kind": "cleanup",
                "level": "caution",
                "confidence": _safe_confidence(item.get("confidence"), 0.5),
                "location": location,
                "root_cause": f"Cleanup candidate categorized as {category}.",
                "evidence": evidence,
                "blast_radius": [path],
                "next_steps_hint": "Review whether the file is still owned and intentionally retained.",
            }
        )
    return concerns


def _archive_concerns(report: dict[str, Any]) -> list[dict[str, Any]]:
    archive = _dict(report.get("archive_candidates"))
    candidates = _list(archive.get("top_candidates"))
    concerns: list[dict[str, Any]] = []
    for item in candidates[:5]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "").strip()
        if not path:
            continue
        category = str(item.get("category", "") or "archive_candidate").strip()
        kind = str(item.get("kind", "") or "").strip()
        tier = str(item.get("archive_tier", "") or "").strip()
        evidence = [f"archive.path={path}"]
        if category:
            evidence.append(f"archive.category={category}")
        if kind:
            evidence.append(f"archive.kind={kind}")
        if tier:
            evidence.append(f"archive.tier={tier}")
        if item.get("review_required") is not None:
            evidence.append(f"archive.review_required={bool(item.get('review_required'))}")
        archive_path_hint = str(item.get("archive_path_hint", "") or "").strip()
        if archive_path_hint:
            evidence.append(f"archive.path_hint={archive_path_hint}")
        location = _location(path)
        concerns.append(
            {
                "concern_id": _stable_concern_id(
                    "cleanup",
                    source="archive",
                    location=location,
                    evidence=evidence,
                ),
                "kind": "cleanup",
                "level": "caution",
                "confidence": _safe_confidence(item.get("confidence"), 0.5),
                "location": location,
                "root_cause": "File is present in the current archive candidate set.",
                "evidence": evidence,
                "blast_radius": [path],
                "next_steps_hint": "Review ownership and active references before changing retention.",
            }
        )
    return concerns


def _hotspot_concerns(report: dict[str, Any]) -> list[dict[str, Any]]:
    concerns: list[dict[str, Any]] = []
    for item in _list(report.get("hotspots"))[:8]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "") or "").strip()
        if not path:
            continue
        component = str(item.get("component", "") or "").strip()
        metric = str(item.get("structure_impact", "") or item.get("dominant_metric", "") or "").strip()
        evidence = [f"hotspot.path={path}"]
        rank = item.get("rank")
        if rank is not None:
            evidence.append(f"hotspot.rank={rank}")
        if component:
            evidence.append(f"hotspot.component={component}")
        if metric:
            evidence.append(f"hotspot.metric={metric}")
        location = _location(path)
        concerns.append(
            {
                "concern_id": _stable_concern_id(
                    "hotspot",
                    source="hotspot",
                    location=location,
                    evidence=evidence,
                ),
                "kind": "hotspot",
                "level": "caution",
                "confidence": _safe_confidence(item.get("confidence"), 0.7),
                "location": location,
                "root_cause": "File appears in the current hotspot set.",
                "evidence": evidence,
                "blast_radius": [path],
                "next_steps_hint": "Review hotspot pressure before expanding this file.",
            }
        )
    return concerns


def _path_from_item(item: object) -> str:
    if isinstance(item, dict):
        return str(item.get("path", "") or item.get("from", "") or "").strip()
    return str(item or "").strip()


def _topology_concerns(report: dict[str, Any]) -> list[dict[str, Any]]:
    topology = _dict(report.get("topology"))
    if not topology:
        return []
    base_evidence = [
        f"topology.source_root={str(topology.get('source_root', '') or '')}",
        f"topology.needs_folder_management={bool(topology.get('needs_folder_management', False))}",
        f"topology.flat_file_total={int(topology.get('flat_file_total', 0) or 0)}",
    ]
    concerns: list[dict[str, Any]] = []

    root_review = _dict(topology.get("root_placement_review"))
    for field in ("misplaced_root_files", "review_root_files"):
        for item in _list(root_review.get(field))[:4]:
            path = _path_from_item(item)
            if not path:
                continue
            evidence = [*base_evidence, f"topology.root_placement={field}"]
            concerns.append(_topology_concern(path, evidence, topology.get("confidence")))

    migration = _dict(topology.get("migration_plan"))
    for item in _list(migration.get("file_moves"))[:4]:
        path = _path_from_item(item)
        if not path:
            continue
        evidence = [*base_evidence, f"topology.file_move.from={path}"]
        if isinstance(item, dict) and str(item.get("to", "") or "").strip():
            evidence.append(f"topology.file_move.to={str(item.get('to', '') or '').strip()}")
        concerns.append(_topology_concern(path, evidence, topology.get("confidence")))
    for item in _list(migration.get("review_files"))[:4]:
        path = _path_from_item(item)
        if not path:
            continue
        evidence = [*base_evidence, "topology.migration_plan=review_files"]
        concerns.append(_topology_concern(path, evidence, topology.get("confidence")))

    for group in _list(topology.get("groups"))[:4]:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("group_id", "") or "").strip()
        for path in _list(group.get("candidate_files"))[:3]:
            path_text = str(path or "").strip()
            if not path_text:
                continue
            evidence = [*base_evidence]
            if group_id:
                evidence.append(f"topology.group_id={group_id}")
            concerns.append(_topology_concern(path_text, evidence, topology.get("confidence")))
    return concerns


def _topology_concern(
    path: str,
    evidence: list[str],
    confidence: object,
) -> dict[str, Any]:
    location = _location(path)
    return {
        "concern_id": _stable_concern_id(
            "boundary",
            source="topology",
            location=location,
            evidence=evidence,
        ),
        "kind": "boundary",
        "level": "caution",
        "confidence": _safe_confidence(confidence, 0.6),
        "location": location,
        "root_cause": "File is part of the current topology review evidence.",
        "evidence": evidence,
        "blast_radius": [path],
        "next_steps_hint": "Review the package boundary before adding more responsibility here.",
    }


def _ranked_concerns(concerns: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    level_weight = {"high-concern": 3, "caution": 2, "info": 1}

    def base_key(item: dict[str, Any]) -> tuple[int, float, int, str]:
        location = _dict(item.get("location"))
        path = str(location.get("path", "") or "")
        return (
            level_weight.get(str(item.get("level", "") or ""), 0),
            _safe_confidence(item.get("confidence"), 0.0),
            1 if path else 0,
            path,
        )

    sorted_concerns = sorted(
        concerns,
        key=lambda item: (-base_key(item)[0], -base_key(item)[1], -base_key(item)[2], base_key(item)[3]),
    )
    levels = sorted(
        {level_weight.get(str(item.get("level", "") or ""), 0) for item in sorted_concerns},
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    for level in levels:
        if len(selected) >= limit:
            break
        group = [
            item
            for item in sorted_concerns
            if level_weight.get(str(item.get("level", "") or ""), 0) == level
        ]
        level_selected: list[dict[str, Any]] = []
        by_kind: dict[str, int] = {}
        for item in group:
            kind = str(item.get("kind", "") or "unknown")
            if by_kind.get(kind, 0) >= CONCERN_KIND_SOFT_CAP:
                continue
            level_selected.append(item)
            by_kind[kind] = by_kind.get(kind, 0) + 1
            if len(selected) + len(level_selected) >= limit:
                break
        if len(selected) + len(level_selected) < limit:
            selected_ids = {id(item) for item in level_selected}
            for item in group:
                if id(item) in selected_ids:
                    continue
                level_selected.append(item)
                if len(selected) + len(level_selected) >= limit:
                    break
        selected.extend(level_selected)
    return selected[:limit]


def _evidence_value(concern: dict[str, Any], prefix: str) -> str:
    for item in _list(concern.get("evidence")):
        text = str(item)
        if text.startswith(prefix):
            return text.split("=", 1)[1]
    return ""


def _has_evidence_prefix(concern: dict[str, Any], prefix: str) -> bool:
    return bool(_evidence_value(concern, prefix))


def _cleanup_archive_category(concern: dict[str, Any]) -> str:
    return (
        _evidence_value(concern, "cleanup.category=")
        or _evidence_value(concern, "archive.category=")
    ).strip()


def _is_cleanup_archive_display_concern(concern: dict[str, Any]) -> bool:
    if str(concern.get("kind", "") or "") != "cleanup":
        return False
    return _has_evidence_prefix(concern, "cleanup.category=") or _has_evidence_prefix(
        concern,
        "archive.category=",
    )


def _is_changelog_like_path(path: str) -> bool:
    text = path.lower().replace("\\", "/")
    name = Path(text).name.replace("_", "-")
    return bool(
        name in {"changelog.md", "changes.md", "history.md", "release-notes.md", "releasenotes.md"}
        or "changelog" in name
        or "release-notes" in text
        or "release_notes" in text
    )


def _has_active_changelog_marker(project_root: str | Path | None, path: str) -> bool:
    if project_root is None:
        return False
    try:
        text = (Path(project_root) / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    marker = re.compile(
        r"(?im)^\s{0,3}#{1,4}\s+"
        r"(?:\[?(?:unreleased|current|next)\]?|\[?v?\d+\.\d+(?:\.\d+)?\]?|\d{4}-\d{2}-\d{2})"
    )
    dated_heading = re.compile(r"(?im)^\s{0,3}#{1,4}\s+.*\d{4}-\d{2}-\d{2}")
    return bool(marker.search(text) or dated_heading.search(text))


def _is_active_changelog_stale_doc_concern(
    concern: dict[str, Any],
    *,
    project_root: str | Path | None,
) -> bool:
    category = _cleanup_archive_category(concern)
    if category != "stale_doc":
        return False
    path = _concern_location_path(concern)
    return bool(
        path
        and _is_changelog_like_path(path)
        and _has_active_changelog_marker(project_root, path)
    )


def _semantic_keep_active_paths(report: dict[str, Any]) -> set[str]:
    semantic_judge = _dict(report.get("semantic_judge"))
    if str(semantic_judge.get("status", "") or "").strip().lower() != "ok":
        return set()
    out: set[str] = set()
    for collection_name in ("judgments", "top_judgments"):
        for item in _list(semantic_judge.get(collection_name)):
            if not isinstance(item, dict):
                continue
            if str(item.get("decision", "") or "").strip().lower() != "keep_active":
                continue
            path = str(item.get("path", "") or "").strip().lstrip("./")
            if path:
                out.add(path)
    return out


def _semantic_review_paths(report: dict[str, Any]) -> set[str]:
    semantic_judge = _dict(report.get("semantic_judge"))
    if str(semantic_judge.get("status", "") or "").strip().lower() != "ok":
        return set()
    out: set[str] = set()
    for collection_name in ("judgments", "top_judgments"):
        for item in _list(semantic_judge.get(collection_name)):
            if not isinstance(item, dict):
                continue
            if str(item.get("decision", "") or "").strip().lower() != "review":
                continue
            path = str(item.get("path", "") or "").strip().lstrip("./")
            if path:
                out.add(path)
    return out


def _semantic_archive_retire_decisions(report: dict[str, Any]) -> dict[str, str]:
    semantic_judge = _dict(report.get("semantic_judge"))
    if str(semantic_judge.get("status", "") or "").strip().lower() != "ok":
        return {}
    decisions: dict[str, str] = {}
    for collection_name in ("judgments", "top_judgments"):
        for item in _list(semantic_judge.get(collection_name)):
            if not isinstance(item, dict):
                continue
            decision = str(item.get("decision", "") or "").strip().lower()
            if decision not in {"archive_first", "retire_now"}:
                continue
            path = str(item.get("path", "") or "").strip().lstrip("./")
            if not path:
                continue
            if decisions.get(path) == "retire_now":
                continue
            decisions[path] = decision
    return decisions


def _semantic_archive_retire_confidence_floor(decision: str) -> float:
    if decision == "retire_now":
        return SEMANTIC_RETIRE_NOW_CONFIDENCE_FLOOR
    return SEMANTIC_ARCHIVE_FIRST_CONFIDENCE_FLOOR


def _apply_semantic_review_context(
    concerns: list[dict[str, Any]],
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    review_paths = _semantic_review_paths(report)
    archive_retire_decisions = _semantic_archive_retire_decisions(report)
    if not review_paths and not archive_retire_decisions:
        return concerns
    enriched: list[dict[str, Any]] = []
    for concern in concerns:
        path = _concern_location_path(concern)
        if (
            path
            and path in review_paths
            and _is_cleanup_archive_display_concern(concern)
        ):
            item = dict(concern)
            evidence = [str(part) for part in _list(item.get("evidence"))]
            if "semantic_judge.decision=review" not in evidence:
                evidence.append("semantic_judge.decision=review")
            item["evidence"] = evidence
            item["confidence"] = max(
                _safe_confidence(item.get("confidence"), 0.0),
                SEMANTIC_REVIEW_CONFIDENCE_FLOOR,
            )
            enriched.append(item)
        elif (
            path
            and path in archive_retire_decisions
            and _is_cleanup_archive_display_concern(concern)
        ):
            decision = archive_retire_decisions[path]
            item = dict(concern)
            evidence = [str(part) for part in _list(item.get("evidence"))]
            fact = f"semantic_judge.decision={decision}"
            if fact not in evidence:
                evidence.append(fact)
            item["evidence"] = evidence
            item["confidence"] = max(
                _safe_confidence(item.get("confidence"), 0.0),
                _semantic_archive_retire_confidence_floor(decision),
            )
            enriched.append(item)
        else:
            enriched.append(concern)
    return enriched


def _is_semantic_keep_active_stale_doc_concern(
    concern: dict[str, Any],
    *,
    keep_active_paths: set[str],
) -> bool:
    if _cleanup_archive_category(concern) != "stale_doc":
        return False
    path = _concern_location_path(concern)
    return bool(path and path in keep_active_paths)


def _is_small_flat_topology_concern(concern: dict[str, Any]) -> bool:
    if str(concern.get("kind", "") or "") != "boundary":
        return False
    if not _has_evidence_prefix(concern, "topology.needs_folder_management="):
        return False
    needs_folder_management = _evidence_value(
        concern,
        "topology.needs_folder_management=",
    ).lower() == "true"
    try:
        flat_file_total = int(_evidence_value(concern, "topology.flat_file_total=") or 0)
    except ValueError:
        return False
    return not needs_folder_management and flat_file_total <= SMALL_FLAT_TOPOLOGY_FILE_LIMIT


def _cleanup_archive_display_key(concern: dict[str, Any]) -> tuple[str, str] | None:
    if not _is_cleanup_archive_display_concern(concern):
        return None
    path = _concern_location_path(concern)
    category = _cleanup_archive_category(concern)
    if not path or not category:
        return None
    return (path, category)


def _preferred_cleanup_archive_concern(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    current_key = (
        _safe_confidence(current.get("confidence"), 0.0),
        str(current.get("concern_id", "") or ""),
    )
    candidate_key = (
        _safe_confidence(candidate.get("confidence"), 0.0),
        str(candidate.get("concern_id", "") or ""),
    )
    return candidate if candidate_key > current_key else current


def _dedupe_cleanup_archive_display_concerns(
    concerns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for concern in concerns:
        key = _cleanup_archive_display_key(concern)
        if key is None:
            passthrough.append(concern)
            continue
        if key in deduped:
            deduped[key] = _preferred_cleanup_archive_concern(deduped[key], concern)
        else:
            deduped[key] = concern
    return [*passthrough, *deduped.values()]


def _calibrated_full_review_display_concerns(
    concerns: list[dict[str, Any]],
    *,
    report: dict[str, Any],
    project_root: str | Path | None,
) -> list[dict[str, Any]]:
    keep_active_paths = _semantic_keep_active_paths(report)
    calibrated = [
        concern
        for concern in concerns
        if not _is_active_changelog_stale_doc_concern(concern, project_root=project_root)
        and not _is_semantic_keep_active_stale_doc_concern(
            concern,
            keep_active_paths=keep_active_paths,
        )
        and not _is_small_flat_topology_concern(concern)
    ]
    return _dedupe_cleanup_archive_display_concerns(calibrated)


def _truncate_list_field(
    item: dict[str, Any],
    field: str,
    *,
    limit: int,
    concern_id: str,
    metadata: list[dict[str, Any]],
) -> None:
    values = _list(item.get(field))
    if len(values) <= limit:
        return
    item[field] = values[:limit]
    metadata.append(
        {
            "concern_id": concern_id,
            "field": field,
            "original_total": len(values),
            "kept": limit,
        }
    )


def _compact_concern_payload(
    concerns: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    compacted: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for concern in concerns:
        item = dict(concern)
        concern_id = str(item.get("concern_id", "") or "")
        _truncate_list_field(
            item,
            "evidence",
            limit=CONCERN_EVIDENCE_LIMIT,
            concern_id=concern_id,
            metadata=metadata,
        )
        _truncate_list_field(
            item,
            "blast_radius",
            limit=CONCERN_BLAST_RADIUS_LIMIT,
            concern_id=concern_id,
            metadata=metadata,
        )
        _truncate_list_field(
            item,
            "references",
            limit=CONCERN_REFERENCES_LIMIT,
            concern_id=concern_id,
            metadata=metadata,
        )
        compacted.append(item)
    return compacted, metadata


def _compact_signal_payload(
    signals: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    compacted: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for signal in signals:
        item = dict(signal)
        kind = str(item.get("kind", "") or "")
        metrics = _dict(item.get("metrics"))
        compact_metrics: dict[str, Any] = {}
        for key, value in metrics.items():
            if isinstance(value, dict) and len(value) > SIGNAL_METRIC_DICT_LIMIT:
                sorted_items = sorted(value.items(), key=lambda entry: str(entry[0]))
                compact_metrics[key] = dict(sorted_items[:SIGNAL_METRIC_DICT_LIMIT])
                metadata.append(
                    {
                        "signal": kind,
                        "metric": str(key),
                        "original_total": len(value),
                        "kept": SIGNAL_METRIC_DICT_LIMIT,
                    }
                )
            else:
                compact_metrics[key] = value
        item["metrics"] = compact_metrics
        compacted.append(item)
    return compacted, metadata


def _payload_bytes(result: dict[str, Any]) -> int:
    payload = {key: value for key, value in result.items() if key != "artifacts"}
    return len(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))


def _finalize_payload(result: dict[str, Any]) -> dict[str, Any]:
    concerns, concern_truncation = _compact_concern_payload(_list(result.get("concerns")))
    signals, signal_truncation = _compact_signal_payload(_list(result.get("signals")))
    result["concerns"] = concerns
    result["signals"] = signals
    result["evidence"] = _evidence(concerns)
    if concern_truncation or signal_truncation:
        artifacts = _dict(result.get("artifacts"))
        result["artifacts"] = artifacts
        metadata: dict[str, Any] = {}
        if concern_truncation:
            metadata["concerns"] = concern_truncation
        if signal_truncation:
            metadata["signals"] = signal_truncation
        artifacts["payload_truncation"] = metadata
    summary = _dict(result.get("summary"))
    result["summary"] = summary
    summary["payload_bytes"] = _payload_bytes(result)
    return result


def _write_concerns_artifact(
    project_root: str | Path | None,
    result: dict[str, Any],
    generated_concerns: list[dict[str, Any]],
) -> None:
    if project_root is None:
        return
    artifacts = _dict(result.get("artifacts"))
    result["artifacts"] = artifacts
    summary = _dict(result.get("summary"))
    artifact = {
        "mode": str(result.get("mode", "") or ""),
        "review_type": str(result.get("review_type", "") or ""),
        "concern_total": len(generated_concerns),
        "concern_limit": int(summary.get("concern_limit", CONCERN_LIMIT) or CONCERN_LIMIT),
        "top_concern_total": int(summary.get("top_concern_total", 0) or 0),
        "scores": _dict(result.get("scores")),
        "summary": {
            "headline": str(summary.get("headline", "") or ""),
            "signal_kinds": _list(summary.get("signal_kinds")),
        },
        "concerns": generated_concerns,
    }
    path = Path(project_root) / ".architec" / CONCERNS_ARTIFACT_FILE
    try:
        write_json(path, artifact)
    except OSError as exc:
        artifacts["code_review_concerns_error"] = str(exc)
    else:
        artifacts["code_review_concerns_json"] = str(path)


def _discovery_from_near_duplicate(scan: dict[str, Any]) -> list[dict[str, Any]]:
    discovery = _dict(scan.get("discovery"))
    return [item for item in _list(discovery.get("candidates")) if isinstance(item, dict)]


def _discovery_from_module_shadow(scan: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in _list(scan.get("candidates")):
        if not isinstance(item, dict):
            continue
        candidate = dict(item)
        candidate["source"] = "shadow_implementation_file_dry_run"
        candidate["reason"] = "module_shadow_candidate"
        candidates.append(candidate)
    return candidates


def _advisory_discovery_scan_for_review(
    report: dict[str, Any],
    *,
    review_type: str,
    project_root: str | Path | None,
    near_duplicate_full_scan: dict[str, Any] | None = None,
    near_duplicate_scope: dict[str, Any] | None,
) -> dict[str, Any]:
    if project_root is None:
        return {}

    candidates: list[dict[str, Any]] = []
    by_source: dict[str, int] = {}
    by_reason: dict[str, int] = {}

    def add_candidates(items: list[dict[str, Any]]) -> None:
        for item in items:
            source = str(item.get("source", "") or "unknown")
            reason = str(item.get("reason", "") or "unknown")
            by_source[source] = by_source.get(source, 0) + 1
            by_reason[reason] = by_reason.get(reason, 0) + 1
            candidates.append(item)

    if review_type in {"diff", "since"}:
        add_candidates(_discovery_from_near_duplicate(_dict(near_duplicate_scope)))
    elif review_type == "full":
        near_scan = _dict(near_duplicate_full_scan)
        if not near_scan:
            near_scan = near_duplicate_scan(project_root, limit=0)
        add_candidates(_discovery_from_near_duplicate(near_scan))
        module_scan = shadow_implementation_file_dry_run(project_root, limit=20)
        add_candidates(_discovery_from_module_shadow(module_scan))

    if not candidates:
        return {}
    return {
        "mode": "advisory_discovery",
        "candidate_total": len(candidates),
        "reported_total": len(candidates),
        "by_source": dict(sorted(by_source.items())),
        "by_reason": dict(sorted(by_reason.items())),
        "candidates": candidates,
    }


def _discovery_candidate_location(candidate: dict[str, Any]) -> dict[str, Any]:
    location = _dict(candidate.get("location"))
    return {
        "path": str(location.get("path", "") or "").strip().lstrip("./"),
        "line": int(location.get("line", 0) or 0),
        "symbol": str(location.get("symbol", "") or ""),
        "symbol_kind": str(location.get("symbol_kind", "") or "function"),
    }


def _promoted_discovery_concern(
    candidate: dict[str, Any],
    factors: list[str],
) -> dict[str, Any] | None:
    source = str(candidate.get("source", "") or "")
    reason = str(candidate.get("reason", "") or "")
    if source != "near_duplicate" or reason not in PROMOTABLE_DISCOVERY_REASONS:
        return None
    location = _discovery_candidate_location(candidate)
    if not location["path"]:
        return None
    reference = _dict(candidate.get("reference"))
    reference_path = str(reference.get("path", "") or "").strip().lstrip("./")
    evidence = [str(item) for item in _list(candidate.get("facts"))]
    evidence.extend(
        [
            f"advisory_discovery.reason={reason}",
            "advisory_discovery.promoted_by=risk_context",
        ]
    )
    for factor in factors:
        evidence.append(f"advisory_discovery.reinforcement={factor}")
    references: list[dict[str, Any]] = []
    if reference_path:
        references.append(
            {
                "role": "reference",
                "path": reference_path,
                "line": int(reference.get("line", 0) or 0),
                "symbol": str(reference.get("symbol", "") or ""),
                "symbol_kind": str(reference.get("symbol_kind", "") or "function"),
            }
        )
    blast_radius = [location["path"]]
    if reference_path and reference_path not in blast_radius:
        blast_radius.append(reference_path)
    return {
        "concern_id": _stable_concern_id(
            "duplication",
            source="advisory_discovery",
            location=location,
            evidence=evidence,
        ),
        "kind": "duplication",
        "level": "info",
        "confidence": 0.68,
        "location": location,
        "root_cause": "Discovery candidate is reinforced by external risk context.",
        "evidence": evidence,
        "references": references,
        "blast_radius": blast_radius,
        "next_steps_hint": "Review whether this wrapper or facade shape should stay separate or share a clearer boundary.",
    }


def _promote_discovery_candidates(
    discovery_scan: dict[str, Any],
    risk_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if risk_context is None or not discovery_scan:
        return []
    promoted: list[dict[str, Any]] = []
    for candidate in _list(discovery_scan.get("candidates")):
        if not isinstance(candidate, dict):
            continue
        location = _discovery_candidate_location(candidate)
        factors = risk_context_reinforcement_factors(risk_context, location.get("path", ""))
        if not factors:
            continue
        concern = _promoted_discovery_concern(candidate, factors)
        if concern is None:
            continue
        candidate["promoted"] = True
        candidate["promotion_reason"] = "risk_context"
        candidate["promotion_factors"] = factors
        promoted.append(concern)
    if promoted:
        discovery_scan["promoted_total"] = len(promoted)
    return promoted


def _write_discovery_artifact(
    project_root: str | Path | None,
    result: dict[str, Any],
    discovery_scan: dict[str, Any],
) -> None:
    if project_root is None or not discovery_scan:
        return
    artifacts = _dict(result.get("artifacts"))
    result["artifacts"] = artifacts
    artifact = {
        "mode": str(result.get("mode", "") or ""),
        "review_type": str(result.get("review_type", "") or ""),
        "summary": {
            "candidate_total": int(discovery_scan.get("candidate_total", 0) or 0),
            "by_source": _dict(discovery_scan.get("by_source")),
            "by_reason": _dict(discovery_scan.get("by_reason")),
            "promoted_total": int(discovery_scan.get("promoted_total", 0) or 0),
        },
        "candidates": _list(discovery_scan.get("candidates")),
    }
    path = Path(project_root) / ".architec" / DISCOVERY_ARTIFACT_FILE
    try:
        write_json(path, artifact)
    except OSError as exc:
        artifacts["code_review_discovery_error"] = str(exc)
    else:
        artifacts["code_review_discovery_json"] = str(path)


def _near_duplicate_total(concerns: list[dict[str, Any]]) -> int:
    return sum(
        1
        for concern in concerns
        if isinstance(concern, dict)
        and str(concern.get("kind", "") or "") == "duplication"
        and any(str(item).startswith("near_duplicate.") for item in _list(concern.get("evidence")))
    )


def _shadow_implementation_items(concerns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        concern
        for concern in concerns
        if isinstance(concern, dict)
        and str(concern.get("kind", "") or "") == "shadow-implementation"
    ]


def _shadow_role(concern: dict[str, Any]) -> str:
    for item in _list(concern.get("evidence")):
        text = str(item)
        if text.startswith("shadow_implementation.role="):
            return text.split("=", 1)[1] or "unknown"
    return "unknown"


def _signals(
    report: dict[str, Any],
    concerns: list[dict[str, Any]],
    *,
    advisory_discovery_scan: dict[str, Any] | None = None,
    architecture_contract_scan_result: dict[str, Any] | None = None,
    near_duplicate_scope: dict[str, Any] | None = None,
    plan_diff_scan: dict[str, Any] | None = None,
    risk_context_scan: dict[str, Any] | None = None,
    shadow_scan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    snapshot_context = _dict(report.get("snapshot_context"))
    if snapshot_context:
        hippo_bundle_present = bool(snapshot_context.get("hippo_bundle_present"))
        hippo_bundle_stale = bool(snapshot_context.get("hippo_bundle_stale"))
        freshness_unknown = bool(snapshot_context.get("freshness_unknown"))
        if not hippo_bundle_present:
            summary = "Incremental review ran without a Hippo structure snapshot."
        elif freshness_unknown:
            summary = "Incremental review used selected-scope evidence; Hippo snapshot freshness could not be determined."
        elif hippo_bundle_stale:
            summary = "Incremental review used selected-scope evidence with a stale Hippo structure snapshot available."
        else:
            summary = "Incremental review used selected-scope evidence with a current Hippo structure snapshot available."
        signals.append(
            {
                "kind": "snapshot_context",
                "summary": summary,
                "metrics": {
                    "hippo_bundle_present": hippo_bundle_present,
                    "hippo_bundle_stale": hippo_bundle_stale,
                    "freshness_unknown": freshness_unknown,
                    "hippo_refresh_performed": bool(snapshot_context.get("hippo_refresh_performed")),
                    "missing_file_total": int(snapshot_context.get("missing_file_total", 0) or 0),
                    "stale_reason_total": int(snapshot_context.get("stale_reason_total", 0) or 0),
                    "selected_file_total": int(snapshot_context.get("selected_file_total", 0) or 0),
                    "selected_changed_after_bundle_total": int(
                        snapshot_context.get("selected_changed_after_bundle_total", 0) or 0
                    ),
                    "stale_reasons": _list(snapshot_context.get("stale_reasons")),
                },
            }
        )
    contract_scan = _dict(architecture_contract_scan_result)
    contract_rule_total = int(contract_scan.get("rule_total", 0) or 0)
    if contract_rule_total:
        contract_concern_total = sum(
            1
            for concern in concerns
            if isinstance(concern, dict)
            and str(concern.get("kind", "") or "") == "architecture-contract"
        )
        signals.append(
            {
                "kind": "architecture_contract",
                "summary": (
                    f"{contract_concern_total} architecture contract concerns detected in changed files."
                ),
                "metrics": {
                    "rule_total": contract_rule_total,
                    "checked_file_total": int(contract_scan.get("checked_file_total", 0) or 0),
                    "concern_total": contract_concern_total,
                    "concern_total_before_limit": int(
                        contract_scan.get("concern_total_before_limit", contract_concern_total) or 0
                    ),
                    "scoped_to_changed_files": bool(contract_scan.get("scoped_to_changed_files")),
                },
            }
        )
    cleanup = _dict(report.get("cleanup"))
    if cleanup:
        candidate_total = int(cleanup.get("candidate_total", 0) or 0)
        review_required_total = int(cleanup.get("review_required_total", 0) or 0)
        owner_total = int(cleanup.get("owner_total", 0) or 0)
        ttl_total = int(cleanup.get("ttl_total", 0) or 0)
        expires_total = int(cleanup.get("expires_total", 0) or 0)
        expired_total = int(cleanup.get("expired_total", 0) or 0)
        signals.append(
            {
                "kind": "cleanup",
                "summary": f"{candidate_total} cleanup candidates; {review_required_total} marked for review.",
                "metrics": {
                    "candidate_total": candidate_total,
                    "review_required_total": review_required_total,
                    "owner_total": owner_total,
                    "ttl_total": ttl_total,
                    "expires_total": expires_total,
                    "expired_total": expired_total,
                    "by_category": _dict(cleanup.get("by_category")),
                },
            }
        )
    archive = _dict(report.get("archive_candidates"))
    if archive:
        candidate_total = int(archive.get("candidate_total", 0) or 0)
        ready_total = int(archive.get("ready_total", 0) or 0)
        review_total = int(archive.get("review_total", 0) or 0)
        signals.append(
            {
                "kind": "archive",
                "summary": f"{candidate_total} archive candidates; {ready_total} ready and {review_total} for review.",
                "metrics": {
                    "candidate_total": candidate_total,
                    "ready_total": ready_total,
                    "review_total": review_total,
                    "by_tier": _dict(archive.get("by_tier")),
                    "by_category": _dict(archive.get("by_category")),
                },
            }
        )
    semantic_judge = _dict(report.get("semantic_judge"))
    if semantic_judge:
        status = str(semantic_judge.get("status", "") or "skipped")
        reviewed_total = int(semantic_judge.get("reviewed_total", 0) or 0)
        candidate_pool_total = int(semantic_judge.get("candidate_pool_total", 0) or 0)
        signals.append(
            {
                "kind": "semantic_judge",
                "summary": f"Semantic judge status {status}; reviewed {reviewed_total} candidates.",
                "metrics": {
                    "status": status,
                    "reviewed_total": reviewed_total,
                    "candidate_pool_total": candidate_pool_total,
                    "by_decision": _dict(semantic_judge.get("by_decision")),
                },
            }
        )
    hotspots = _list(report.get("hotspots"))
    if hotspots:
        signals.append(
            {
                "kind": "hotspot",
                "summary": f"{len(hotspots)} hotspot items detected.",
                "metrics": {"item_total": len(hotspots)},
            }
        )
    topology = _dict(report.get("topology"))
    if topology:
        needs_folder_management = bool(topology.get("needs_folder_management", False))
        flat_file_total = int(topology.get("flat_file_total", 0) or 0)
        summary = "Topology review data available."
        if needs_folder_management:
            summary = "Topology review suggests folder management attention."
        signals.append(
            {
                "kind": "topology",
                "summary": summary,
                "metrics": {
                    "needs_folder_management": needs_folder_management,
                    "flat_file_total": flat_file_total,
                },
            }
        )
    near_duplicate_total = _near_duplicate_total(concerns)
    if near_duplicate_total:
        scoped = _dict(near_duplicate_scope) if near_duplicate_scope is not None else {}
        metrics: dict[str, Any] = {"concern_total": near_duplicate_total}
        if scoped.get("scoped_to_changed_files"):
            metrics["scoped_to_changed_files"] = True
            metrics["changed_file_total"] = int(scoped.get("changed_file_total", 0) or 0)
            metrics["candidate_total_before_scope"] = int(
                scoped.get("candidate_total_before_scope", near_duplicate_total) or 0
            )
        scan_cache = _dict(scoped.get("scan_cache"))
        if scan_cache:
            metrics["scan_cache"] = scan_cache
        signals.append(
            {
                "kind": "near_duplicate",
                "summary": (
                    f"{near_duplicate_total} near-duplicate function concerns detected in changed files."
                    if scoped.get("scoped_to_changed_files")
                    else f"{near_duplicate_total} near-duplicate function concerns detected."
                ),
                "metrics": metrics,
            }
        )
    shadow_items = _shadow_implementation_items(concerns)
    if shadow_items:
        by_role: dict[str, int] = {}
        by_symbol_kind: dict[str, int] = {}
        for concern in shadow_items:
            role = _shadow_role(concern)
            by_role[role] = by_role.get(role, 0) + 1
            location = _dict(concern.get("location"))
            symbol_kind = str(location.get("symbol_kind", "") or "unknown")
            by_symbol_kind[symbol_kind] = by_symbol_kind.get(symbol_kind, 0) + 1
        high_confidence_total = sum(
            1
            for concern in shadow_items
            if _safe_confidence(concern.get("confidence"), 0.0) >= 0.78
        )
        metrics: dict[str, Any] = {
            "candidate_total": len(shadow_items),
            "high_confidence_total": high_confidence_total,
            "by_role": dict(sorted(by_role.items())),
            "by_symbol_kind": dict(sorted(by_symbol_kind.items())),
        }
        scoped = _dict(shadow_scan) if shadow_scan is not None else {}
        if scoped.get("scoped_to_changed_files"):
            metrics["scoped_to_changed_files"] = True
            metrics["changed_file_total"] = int(scoped.get("changed_file_total", 0) or 0)
            metrics["candidate_total_before_scope"] = int(
                scoped.get("candidate_total_before_scope", len(shadow_items)) or 0
            )
        scan_cache = _dict(scoped.get("scan_cache"))
        if scan_cache:
            metrics["scan_cache"] = scan_cache
        summary = (
            f"{len(shadow_items)} shadow implementation candidates detected in changed files."
            if scoped.get("scoped_to_changed_files")
            else f"{len(shadow_items)} shadow implementation candidates detected."
        )
        signals.append(
            {
                "kind": "shadow_implementation",
                "summary": summary,
                "metrics": metrics,
            }
        )
    discovery_scan = _dict(advisory_discovery_scan)
    discovery_total = int(discovery_scan.get("candidate_total", 0) or 0)
    if discovery_total:
        promoted_total = int(discovery_scan.get("promoted_total", 0) or 0)
        summary = f"{discovery_total} advisory discovery candidates available outside primary concerns."
        if promoted_total:
            summary = (
                f"{discovery_total} advisory discovery candidates available; "
                f"{promoted_total} promoted with reinforcing context."
            )
        signals.append(
            {
                "kind": "advisory_discovery",
                "summary": summary,
                "metrics": {
                    "candidate_total": discovery_total,
                    "reported_total": int(discovery_scan.get("reported_total", discovery_total) or 0),
                    "promoted_total": promoted_total,
                    "by_source": _dict(discovery_scan.get("by_source")),
                    "by_reason": _dict(discovery_scan.get("by_reason")),
                },
            }
        )
    plan_scan = _dict(plan_diff_scan)
    planned_path_total = int(plan_scan.get("planned_path_total", 0) or 0)
    planned_import_total = int(plan_scan.get("planned_import_total", 0) or 0)
    expected_test_total = int(plan_scan.get("expected_test_total", 0) or 0)
    public_api_migration_total = int(plan_scan.get("public_api_migration_total", 0) or 0)
    semantic_intent_total = int(plan_scan.get("semantic_intent_total", 0) or 0)
    if planned_path_total or planned_import_total or expected_test_total or public_api_migration_total or semantic_intent_total:
        plan_concern_total = sum(
            1
            for concern in concerns
            if isinstance(concern, dict)
            and str(concern.get("kind", "") or "") == "plan-diff-consistency"
        )
        signals.append(
            {
                "kind": "plan_diff_consistency",
                "summary": f"{plan_concern_total} plan/diff consistency observations detected.",
                "metrics": {
                    "planned_path_total": planned_path_total,
                    "planned_import_total": planned_import_total,
                    "planned_import_alternative_total": int(
                        plan_scan.get("planned_import_alternative_total", 0) or 0
                    ),
                    "observed_planned_import_total": int(
                        plan_scan.get("observed_planned_import_total", 0) or 0
                    ),
                    "missing_planned_import_total": int(
                        plan_scan.get("missing_planned_import_total", 0) or 0
                    ),
                    "expected_test_total": expected_test_total,
                    "observed_expected_test_total": int(
                        plan_scan.get("observed_expected_test_total", 0) or 0
                    ),
                    "missing_expected_test_total": int(
                        plan_scan.get("missing_expected_test_total", 0) or 0
                    ),
                    "public_api_migration_total": public_api_migration_total,
                    "observed_public_api_migration_total": int(
                        plan_scan.get("observed_public_api_migration_total", 0) or 0
                    ),
                    "missing_public_api_migration_total": int(
                        plan_scan.get("missing_public_api_migration_total", 0) or 0
                    ),
                    "semantic_intent_total": semantic_intent_total,
                    "observed_semantic_intent_total": int(
                        plan_scan.get("observed_semantic_intent_total", 0) or 0
                    ),
                    "missing_semantic_intent_total": int(
                        plan_scan.get("missing_semantic_intent_total", 0) or 0
                    ),
                    "conflicting_semantic_intent_total": int(
                        plan_scan.get("conflicting_semantic_intent_total", 0) or 0
                    ),
                    "changed_file_total": int(plan_scan.get("changed_file_total", 0) or 0),
                    "concern_total": plan_concern_total,
                    "concern_total_before_limit": int(
                        plan_scan.get("concern_total_before_limit", plan_concern_total) or 0
                    ),
                    "scoped_to_changed_files": bool(plan_scan.get("scoped_to_changed_files")),
                },
            }
        )
    risk_scan = _dict(risk_context_scan)
    if risk_scan:
        enriched_total = int(risk_scan.get("enriched_concern_total", 0) or 0)
        signals.append(
            {
                "kind": "risk_context",
                "summary": f"{enriched_total} concerns enriched with external risk context.",
                "metrics": {
                    "input_file_total": int(risk_scan.get("input_file_total", 0) or 0),
                    "enriched_concern_total": enriched_total,
                    "changed_test_total": int(risk_scan.get("changed_test_total", 0) or 0),
                    "coverage_file_total": int(risk_scan.get("coverage_file_total", 0) or 0),
                    "churn_file_total": int(risk_scan.get("churn_file_total", 0) or 0),
                    "complexity_file_total": int(risk_scan.get("complexity_file_total", 0) or 0),
                    "public_api_file_total": int(risk_scan.get("public_api_file_total", 0) or 0),
                    "recurrence_file_total": int(risk_scan.get("recurrence_file_total", 0) or 0),
                    "test_map_file_total": int(risk_scan.get("test_map_file_total", 0) or 0),
                    "by_factor": _dict(risk_scan.get("by_factor")),
                },
            }
        )
    return signals


def _evidence(concerns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for index, concern in enumerate(concerns, start=1):
        facts = _list(concern.get("evidence"))
        concern_id = str(concern.get("concern_id", "") or "")
        evidence.append(
            {
                "evidence_id": f"code-review:evidence:{index}",
                "concern_id": concern_id,
                "kind": concern.get("kind", ""),
                "location": concern.get("location", {}),
                "confidence": concern.get("confidence", 0.0),
                "facts": [str(fact) for fact in facts],
            }
        )
    return evidence


def _summary(
    concerns: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    *,
    review_type: str,
    concern_total: int,
    concern_limit: int = CONCERN_LIMIT,
    since_ref: str = "",
    scope_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    if review_type == "since" and not concerns:
        headline = "No new architecture concerns were identified in the selected since range."
    elif review_type == "since":
        headline = f"Since code review complete for {since_ref}."
    elif review_type == "diff" and not concerns:
        headline = "No new architecture concerns were identified in the selected diff."
    elif review_type == "diff":
        headline = "Diff code review complete"
    else:
        headline = "Full code review complete"
    summary = {
        "headline": headline,
        "concern_total": concern_total,
        "top_concern_total": len(concerns),
        "concern_limit": concern_limit,
        "signal_kinds": [str(signal.get("kind", "") or "") for signal in signals if isinstance(signal, dict)],
    }
    if scope_counts is not None:
        summary.update(scope_counts)
    return summary


def _empty_since_range_result(ref: str) -> dict[str, Any]:
    return {
        "mode": "code_review",
        "review_type": "since",
        "scores": {},
        "summary": {
            "headline": "Unable to analyze the requested since range.",
            "reason": "The requested since range could not be resolved.",
            "concern_total": 0,
            "top_concern_total": 0,
            "concern_limit": CONCERN_LIMIT,
            "signal_kinds": [],
        },
        "findings": [],
        "signals": [],
        "evidence": [],
        "concerns": [],
        "artifacts": {},
    }


def _is_since_range_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "bad revision",
        "fatal:",
        "git range error",
        "unknown revision",
        "ambiguous argument",
        "invalid revision",
        "invalid object",
        "could not resolve",
        "no merge base",
        "not a git repository",
        "since range",
    )
    return any(marker in text for marker in markers)


def _static_artifacts(reason: str = "") -> dict[str, Any]:
    artifacts: dict[str, Any] = {"code_review_analysis_mode": "static"}
    reason_text = str(reason or "").strip()
    if reason_text:
        artifacts["code_review_static_reason"] = reason_text
    return artifacts


def _static_full_report(reason: str = "") -> dict[str, Any]:
    return {
        "scores": {},
        "summary": {},
        "cleanup": {},
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [],
        "topology": {},
        "artifacts": _static_artifacts(reason),
    }


def _static_incremental_report(
    project_root: str | Path,
    *,
    base: str = "",
    head: str = "",
    reason: str = "",
) -> dict[str, Any]:
    changed = git_changed_files(Path(project_root), base=base or None, head=head or None)
    changed_files = [
        str(item.get("path", "") or "").strip().lstrip("./")
        for item in changed
        if isinstance(item, dict) and str(item.get("path", "") or "").strip()
    ]
    return {
        "scores": {},
        "summary": {},
        "cleanup": {},
        "archive_candidates": {},
        "semantic_judge": {},
        "hotspots": [],
        "topology": {},
        "change_analysis": {
            "changed_file_total": len(changed_files),
            "changed_files": changed_files,
            "components": [],
        },
        "artifacts": _static_artifacts(reason),
    }


def _parse_snapshot_datetime(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(probe)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _selected_files_changed_after(project_root: Path, changed_files: list[str], generated_at: str) -> int:
    parsed = _parse_snapshot_datetime(generated_at)
    if parsed is None:
        return 0
    reference_ns = int(parsed.timestamp() * 1_000_000_000)
    changed_total = 0
    for raw_path in changed_files:
        rel = str(raw_path or "").strip().lstrip("./")
        if not rel:
            continue
        try:
            if (project_root / rel).stat().st_mtime_ns > reference_ns:
                changed_total += 1
        except OSError:
            continue
    return changed_total


def _incremental_snapshot_context(
    project_root: str | Path,
    *,
    changed_files: list[str],
) -> dict[str, Any]:
    root = Path(project_root)
    missing_files = [rel for rel in REQUIRED_BUNDLE_FILES if not (root / rel).is_file()]
    bundle_present = not missing_files
    state = read_json(root / ".hippocampus" / "bundle-state.json", default={})
    metrics = read_json(root / ".hippocampus" / "architect-metrics.json", default={})
    bundle_generated_at = str(_dict(state).get("generated_at", "") or "").strip()
    metrics_generated_at = str(_dict(metrics).get("generated_at", "") or "").strip()
    reference_generated_at = bundle_generated_at or metrics_generated_at
    freshness_unknown = bool(bundle_present and _parse_snapshot_datetime(reference_generated_at) is None)
    selected_changed_after_bundle_total = (
        _selected_files_changed_after(root, changed_files, reference_generated_at)
        if bundle_present and not freshness_unknown
        else 0
    )
    stale_reasons: list[str] = []
    if selected_changed_after_bundle_total:
        stale_reasons.append(
            "selected files changed after Hippo bundle generation "
            f"(files={selected_changed_after_bundle_total})"
        )
    return {
        "hippo_bundle_present": bundle_present,
        "hippo_bundle_stale": bool(stale_reasons),
        "freshness_unknown": freshness_unknown,
        "hippo_refresh_performed": False,
        "missing_file_total": len(missing_files),
        "stale_reason_total": len(stale_reasons),
        "stale_reasons": stale_reasons[:3],
        "selected_file_total": len(changed_files),
        "selected_changed_after_bundle_total": selected_changed_after_bundle_total,
        "bundle_state_generated_at": bundle_generated_at,
        "metrics_generated_at": metrics_generated_at,
    }


def _mark_incremental_snapshot_context(report: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if context:
        report["snapshot_context"] = context
    return report


def _mark_static_result(
    result: dict[str, Any],
    *,
    reason: str = "",
    review_type: str = "full",
) -> dict[str, Any]:
    summary = _dict(result.get("summary"))
    result["summary"] = summary
    if review_type == "diff":
        summary["headline"] = "Diff analysis was unavailable; static code-review signals were generated."
    elif review_type == "since":
        summary["headline"] = "Since analysis was unavailable; static code-review signals were generated."
    else:
        summary["headline"] = "Full analysis was unavailable; static code-review signals were generated."
    summary["analysis_mode"] = "static"
    reason_text = str(reason or "").strip()
    if reason_text:
        summary["reason"] = reason_text
    artifacts = _dict(result.get("artifacts"))
    result["artifacts"] = artifacts
    artifacts["code_review_analysis_mode"] = "static"
    if reason_text:
        artifacts["code_review_static_reason"] = reason_text
    return result


def _mark_static_full_result(result: dict[str, Any], *, reason: str = "") -> dict[str, Any]:
    return _mark_static_result(result, reason=reason, review_type="full")


def _mark_incremental_llm_report(report: dict[str, Any]) -> dict[str, Any]:
    artifacts = _dict(report.get("artifacts"))
    report["artifacts"] = artifacts
    artifacts["code_review_analysis_mode"] = "incremental_llm"
    artifacts["code_review_llm_context"] = "selected_scope"
    artifacts.pop("code_review_static_reason", None)
    return report


def _compact_llm_concern(concern: dict[str, Any]) -> dict[str, Any]:
    location = _dict(concern.get("location"))
    return {
        "kind": str(concern.get("kind", "") or ""),
        "level": str(concern.get("level", "") or ""),
        "confidence": concern.get("confidence", 0.0),
        "path": str(location.get("path", "") or ""),
        "symbol": str(location.get("symbol", "") or ""),
        "root_cause": str(concern.get("root_cause", "") or ""),
        "evidence": [str(item) for item in _list(concern.get("evidence"))[:4]],
    }


def _compact_llm_signal(signal: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(_dict(signal.get("metrics")))
    metrics.pop("scan_cache", None)
    return {
        "kind": str(signal.get("kind", "") or ""),
        "summary": str(signal.get("summary", "") or ""),
        "metrics": metrics,
    }


def _incremental_llm_payload(
    result: dict[str, Any],
    report: dict[str, Any],
    *,
    changed_files: list[str],
) -> dict[str, Any]:
    summary = _dict(result.get("summary"))
    return {
        "mode": "incremental_code_review",
        "review_type": str(result.get("review_type", "") or "diff"),
        "analysis_context": "selected_scope",
        "changed_file_total": len(changed_files),
        "changed_files": changed_files[:30],
        "summary": {
            "concern_total": int(summary.get("concern_total", 0) or 0),
            "top_concern_total": int(summary.get("top_concern_total", 0) or 0),
            "scoped_concern_total": int(summary.get("scoped_concern_total", 0) or 0),
            "global_context_concern_total": int(summary.get("global_context_concern_total", 0) or 0),
        },
        "concerns": [_compact_llm_concern(item) for item in _list(result.get("concerns"))[:8] if isinstance(item, dict)],
        "signals": [_compact_llm_signal(item) for item in _list(result.get("signals"))[:8] if isinstance(item, dict)],
        "change_analysis": _dict(report.get("change_analysis")),
        "snapshot_context": _dict(report.get("snapshot_context")),
    }


def _string_list(value: object, *, limit: int) -> list[str]:
    out: list[str] = []
    for item in _list(value):
        text = str(item or "").strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _dict_list(value: object, *, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in _list(value):
        if isinstance(item, dict):
            out.append(dict(item))
        if len(out) >= limit:
            break
    return out


def _apply_incremental_llm_summary(
    result: dict[str, Any],
    llm_result: dict[str, Any],
    *,
    selected_file_total: int,
) -> dict[str, Any]:
    summary = _dict(result.get("summary"))
    result["summary"] = summary
    summary["analysis_mode"] = "incremental_llm"
    summary["llm_context"] = "selected_scope"
    headline = str(llm_result.get("headline", "") or "").strip()
    if headline:
        summary["headline"] = headline
    executive_summary = str(llm_result.get("executive_summary", "") or "").strip()
    if executive_summary:
        summary["executive_summary"] = executive_summary
    takeaways = _string_list(llm_result.get("top_takeaways"), limit=3)
    if takeaways:
        summary["top_takeaways"] = takeaways
    recommendations = _dict_list(llm_result.get("recommendations"), limit=5)
    if recommendations:
        result["recommendations"] = recommendations

    artifacts = _dict(result.get("artifacts"))
    result["artifacts"] = artifacts
    artifacts["code_review_analysis_mode"] = "incremental_llm"
    artifacts["code_review_llm_context"] = "selected_scope"

    llm_cache_hit = bool(llm_result.get("_cache_hit", False))
    signals = _list(result.get("signals"))
    signals.append(
        {
            "kind": "cost_context",
            "summary": "Incremental review used bounded selected-scope LLM context.",
            "metrics": {
                "selected_file_total": selected_file_total,
                "llm_call_total": 1,
                "cache_hit_total": 1 if llm_cache_hit else 0,
                "llm_cache_hit_total": 1 if llm_cache_hit else 0,
                "llm_backend_call_total": 0 if llm_cache_hit else 1,
                "analysis_mode": "incremental_llm",
                "llm_context": "selected_scope",
            },
        }
    )
    result["signals"] = signals
    return _finalize_payload(result)


def _changed_files_from_report(report: dict[str, Any]) -> list[str]:
    change = _dict(report.get("change_analysis"))
    raw = _list(change.get("changed_files"))
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        path = str(item or "").strip().lstrip("./")
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _concern_location_path(concern: dict[str, Any]) -> str:
    return str(_dict(concern.get("location")).get("path", "") or "").strip().lstrip("./")


def _is_incremental_selected_scope_concern(
    concern: dict[str, Any],
    changed_files: set[str],
) -> bool:
    kind = str(concern.get("kind", "") or "")
    if kind in INCREMENTAL_SELECTED_SCOPE_KINDS:
        return True
    path = _concern_location_path(concern)
    return bool(path and path in changed_files)


def _display_concerns_for_review(
    concerns: list[dict[str, Any]],
    *,
    report: dict[str, Any],
    review_type: str,
    changed_files: list[str],
    project_root: str | Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int] | None]:
    if review_type not in {"diff", "since"}:
        calibrated = _calibrated_full_review_display_concerns(
            concerns,
            report=report,
            project_root=project_root,
        )
        return _ranked_concerns(calibrated, limit=CONCERN_LIMIT), None

    changed_file_set = set(changed_files)
    scoped: list[dict[str, Any]] = []
    global_context: list[dict[str, Any]] = []
    for concern in concerns:
        if _is_incremental_selected_scope_concern(concern, changed_file_set):
            scoped.append(concern)
        else:
            global_context.append(concern)

    display_scoped = _dedupe_cleanup_archive_display_concerns(scoped)
    display = _ranked_concerns(display_scoped, limit=CONCERN_LIMIT)
    return display, {
        "scoped_concern_total": len(scoped),
        "global_context_concern_total": len(global_context),
        "displayed_scoped_concern_total": len(display),
        "displayed_global_context_concern_total": 0,
    }


def _shadow_scan_for_review(
    report: dict[str, Any],
    *,
    review_type: str,
    project_root: str | Path | None,
) -> dict[str, Any]:
    if project_root is None:
        return {"concerns": []}
    if review_type == "full":
        return shadow_implementation_scan(project_root)
    if review_type in {"diff", "since"}:
        changed_files = _changed_files_from_report(report)
        if changed_files:
            return shadow_implementation_scan(project_root, changed_files=changed_files)
    return {"concerns": []}


def _near_duplicate_scan_for_review(
    report: dict[str, Any],
    *,
    review_type: str,
    project_root: str | Path | None,
) -> dict[str, Any]:
    if project_root is None:
        return {"concerns": []}
    if review_type in {"diff", "since"}:
        changed_files = _changed_files_from_report(report)
        if changed_files:
            return near_duplicate_scan(project_root, changed_files=changed_files)
    return {"concerns": []}


def _architecture_contract_scan_for_review(
    report: dict[str, Any],
    *,
    review_type: str,
    project_root: str | Path | None,
) -> dict[str, Any]:
    if project_root is None or review_type not in {"diff", "since"}:
        return {"concerns": []}
    changed_files = _changed_files_from_report(report)
    if not changed_files:
        return {"concerns": []}
    return architecture_contract_scan(project_root, changed_files=changed_files)


def _plan_diff_scan_for_review(
    report: dict[str, Any],
    *,
    review_type: str,
    plan_review: dict[str, Any] | None,
    project_root: str | Path | None,
) -> dict[str, Any]:
    if plan_review is None or review_type not in {"diff", "since"}:
        return {"concerns": []}
    changed_files = _changed_files_from_report(report)
    return plan_diff_consistency_scan(
        plan_review,
        changed_files=changed_files,
        project_root=project_root,
    )


def _result_from_report(
    report: dict[str, Any],
    *,
    review_type: str,
    since_ref: str = "",
    project_root: str | Path | None = None,
    plan_review: dict[str, Any] | None = None,
    risk_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    near_duplicate_full_scan = (
        near_duplicate_scan(project_root)
        if review_type == "full" and project_root is not None
        else None
    )
    duplicate_concerns = list(_dict(near_duplicate_full_scan).get("concerns", []))
    near_duplicate_scope = _near_duplicate_scan_for_review(
        report,
        review_type=review_type,
        project_root=project_root,
    )
    duplicate_concerns.extend(list(near_duplicate_scope.get("concerns", [])))
    shadow_scan = _shadow_scan_for_review(
        report,
        review_type=review_type,
        project_root=project_root,
    )
    shadow_concerns = list(shadow_scan.get("concerns", []))
    architecture_scan = _architecture_contract_scan_for_review(
        report,
        review_type=review_type,
        project_root=project_root,
    )
    architecture_concerns = list(architecture_scan.get("concerns", []))
    plan_diff_scan = _plan_diff_scan_for_review(
        report,
        review_type=review_type,
        plan_review=plan_review,
        project_root=project_root,
    )
    plan_diff_concerns = list(plan_diff_scan.get("concerns", []))
    advisory_discovery_scan = _advisory_discovery_scan_for_review(
        report,
        review_type=review_type,
        project_root=project_root,
        near_duplicate_full_scan=near_duplicate_full_scan,
        near_duplicate_scope=near_duplicate_scope,
    )
    promoted_discovery_concerns = _promote_discovery_candidates(
        advisory_discovery_scan,
        risk_context,
    )
    generated_concerns = [
        *_cleanup_concerns(report),
        *_archive_concerns(report),
        *_hotspot_concerns(report),
        *_topology_concerns(report),
        *duplicate_concerns,
        *shadow_concerns,
        *architecture_concerns,
        *plan_diff_concerns,
        *promoted_discovery_concerns,
    ]
    generated_concerns = _apply_semantic_review_context(generated_concerns, report)
    generated_concerns, risk_scan = apply_risk_context(generated_concerns, risk_context)
    changed_files = _changed_files_from_report(report)
    concerns, scope_counts = _display_concerns_for_review(
        generated_concerns,
        report=report,
        review_type=review_type,
        changed_files=changed_files,
        project_root=project_root,
    )
    signals = _signals(
        report,
        generated_concerns,
        advisory_discovery_scan=advisory_discovery_scan,
        architecture_contract_scan_result=architecture_scan,
        near_duplicate_scope=near_duplicate_scope,
        plan_diff_scan=plan_diff_scan,
        risk_context_scan=risk_scan,
        shadow_scan=shadow_scan,
    )
    result = {
        "mode": "code_review",
        "review_type": review_type,
        "scores": _dict(report.get("scores")),
        "summary": _summary(
            concerns,
            signals,
            review_type=review_type,
            concern_total=len(generated_concerns),
            concern_limit=CONCERN_LIMIT,
            since_ref=since_ref,
            scope_counts=scope_counts,
        ),
        "findings": [],
        "signals": signals,
        "evidence": [],
        "concerns": concerns,
        "artifacts": _dict(report.get("artifacts")),
    }
    _write_concerns_artifact(project_root, result, generated_concerns)
    _write_discovery_artifact(project_root, result, advisory_discovery_scan)
    return _finalize_payload(result)


def _with_review_event(project_root: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    artifacts = _dict(result.get("artifacts"))
    result["artifacts"] = artifacts
    try:
        event_path = append_review_event(project_root, result)
    except OSError as exc:
        artifacts["review_event_error"] = str(exc)
    else:
        artifacts["review_event_jsonl"] = str(event_path)
    return result


def run_code_review_full(
    project_root: str | Path,
    *,
    risk_context_path: str | Path | None = None,
    advice_feedback_path: str | Path | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    analysis_kwargs: dict[str, Any] = {
        "goal": "",
        "diff": False,
        "base": "",
        "head": "",
        "progress": progress,
    }
    if advice_feedback_path:
        analysis_kwargs["advice_feedback_path"] = advice_feedback_path
    report = run_analysis(
        project_root,
        **analysis_kwargs,
    )
    risk_context = load_risk_context(risk_context_path) if risk_context_path else None
    result = _result_from_report(
        report,
        review_type="full",
        project_root=project_root,
        risk_context=risk_context,
    )
    return _with_review_event(project_root, result)


def run_code_review_static_full(
    project_root: str | Path,
    *,
    reason: str = "",
    risk_context_path: str | Path | None = None,
    advice_feedback_path: str | Path | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    del advice_feedback_path
    if progress is not None:
        progress("code-review static [1/1] generating deterministic signals")
    risk_context = load_risk_context(risk_context_path) if risk_context_path else None
    result = _result_from_report(
        _static_full_report(reason),
        review_type="full",
        project_root=project_root,
        risk_context=risk_context,
    )
    result = _mark_static_full_result(result, reason=reason)
    return _with_review_event(project_root, _finalize_payload(result))


def run_code_review_static_diff(
    project_root: str | Path,
    *,
    base: str = "",
    head: str = "",
    reason: str = "",
    plan_review_path: str | Path | None = None,
    risk_context_path: str | Path | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    if progress is not None:
        progress("code-review static [1/1] generating deterministic diff signals")
    plan_review = load_plan_review(plan_review_path) if plan_review_path else None
    risk_context = load_risk_context(risk_context_path) if risk_context_path else None
    result = _result_from_report(
        _static_incremental_report(project_root, base=base, head=head, reason=reason),
        review_type="diff",
        project_root=project_root,
        plan_review=plan_review,
        risk_context=risk_context,
    )
    result = _mark_static_result(result, reason=reason, review_type="diff")
    return _with_review_event(project_root, _finalize_payload(result))


def run_code_review_incremental_llm(
    project_root: str | Path,
    *,
    base: str = "",
    head: str = "",
    plan_review_path: str | Path | None = None,
    risk_context_path: str | Path | None = None,
    progress: ProgressFn | None = None,
    ) -> dict[str, Any]:
    if progress is not None:
        progress("code-review incremental [1/3] collecting selected changes")
    report = _mark_incremental_llm_report(
        _static_incremental_report(project_root, base=base, head=head),
    )
    changed_files = _changed_files_from_report(report)
    snapshot_context = _incremental_snapshot_context(
        project_root,
        changed_files=changed_files,
    )
    report = _mark_incremental_snapshot_context(report, snapshot_context)
    plan_review = load_plan_review(plan_review_path) if plan_review_path else None
    risk_context = load_risk_context(risk_context_path) if risk_context_path else None
    if progress is not None:
        progress("code-review incremental [2/3] generating selected-scope evidence")
    result = _result_from_report(
        report,
        review_type="diff",
        project_root=project_root,
        plan_review=plan_review,
        risk_context=risk_context,
    )
    payload = _incremental_llm_payload(result, report, changed_files=changed_files)
    if progress is not None:
        progress("code-review incremental [3/3] requesting selected-scope LLM summary")
    llm_result = incremental_llm_summary(Path(project_root).resolve(), payload=payload) or {}
    result = _apply_incremental_llm_summary(
        result,
        llm_result,
        selected_file_total=len(changed_files),
    )
    return _with_review_event(project_root, result)


def run_code_review_diff(
    project_root: str | Path,
    *,
    base: str = "",
    head: str = "",
    plan_review_path: str | Path | None = None,
    risk_context_path: str | Path | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    report = run_analysis(
        project_root,
        goal="",
        diff=True,
        base=str(base or "").strip(),
        head=str(head or "").strip(),
        progress=progress,
    )
    plan_review = load_plan_review(plan_review_path) if plan_review_path else None
    risk_context = load_risk_context(risk_context_path) if risk_context_path else None
    result = _result_from_report(
        report,
        review_type="diff",
        project_root=project_root,
        plan_review=plan_review,
        risk_context=risk_context,
    )
    return _with_review_event(project_root, result)


def run_code_review_static_since(
    project_root: str | Path,
    *,
    ref: str,
    reason: str = "",
    plan_review_path: str | Path | None = None,
    risk_context_path: str | Path | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    since_ref = str(ref or "").strip()
    if progress is not None:
        progress("code-review static [1/1] generating deterministic since signals")
    try:
        report = _static_incremental_report(
            project_root,
            base=since_ref,
            head="HEAD",
            reason=reason,
        )
    except RuntimeError as exc:
        if not _is_since_range_error(exc):
            raise
        return _empty_since_range_result(since_ref)
    plan_review = load_plan_review(plan_review_path) if plan_review_path else None
    risk_context = load_risk_context(risk_context_path) if risk_context_path else None
    result = _result_from_report(
        report,
        review_type="since",
        since_ref=since_ref,
        project_root=project_root,
        plan_review=plan_review,
        risk_context=risk_context,
    )
    result = _mark_static_result(result, reason=reason, review_type="since")
    return _with_review_event(project_root, _finalize_payload(result))


def run_code_review_since(
    project_root: str | Path,
    *,
    ref: str,
    plan_review_path: str | Path | None = None,
    risk_context_path: str | Path | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    since_ref = str(ref or "").strip()
    try:
        report = run_analysis(
            project_root,
            goal="",
            diff=True,
            base=since_ref,
            head="HEAD",
            progress=progress,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        if not _is_since_range_error(exc):
            raise
        return _empty_since_range_result(since_ref)
    plan_review = load_plan_review(plan_review_path) if plan_review_path else None
    risk_context = load_risk_context(risk_context_path) if risk_context_path else None
    result = _result_from_report(
        report,
        review_type="since",
        since_ref=since_ref,
        project_root=project_root,
        plan_review=plan_review,
        risk_context=risk_context,
    )
    return _with_review_event(project_root, result)


__all__ = [
    "run_code_review_diff",
    "run_code_review_full",
    "run_code_review_incremental_llm",
    "run_code_review_static_diff",
    "run_code_review_static_full",
    "run_code_review_static_since",
    "run_code_review_since",
]
