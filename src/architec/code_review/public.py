from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from architec.analysis.public import run_analysis
from architec.code_review.near_duplicate import near_duplicate_concerns
from architec.code_review.shadow_implementation import shadow_implementation_scan
from architec.events.public import append_review_event
from architec.support.io_utils import ProgressFn, clamp


CONCERN_LIMIT = 5


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

    def sort_key(item: dict[str, Any]) -> tuple[int, float, int, str]:
        location = _dict(item.get("location"))
        path = str(location.get("path", "") or "")
        return (
            level_weight.get(str(item.get("level", "") or ""), 0),
            _safe_confidence(item.get("confidence"), 0.0),
            1 if path else 0,
            path,
        )

    return sorted(concerns, key=sort_key, reverse=True)[:limit]


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
    shadow_scan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
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
        signals.append(
            {
                "kind": "near_duplicate",
                "summary": f"{near_duplicate_total} near-duplicate function concerns detected.",
                "metrics": {"concern_total": near_duplicate_total},
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
) -> dict[str, Any]:
    if review_type == "since" and not concerns:
        headline = f"No new architecture concerns were identified since {since_ref}."
    elif review_type == "since":
        headline = f"Since code review complete for {since_ref}."
    elif review_type == "diff" and not concerns:
        headline = "No new architecture concerns were identified in this diff."
    elif review_type == "diff":
        headline = "Diff code review complete"
    else:
        headline = "Full code review complete"
    return {
        "headline": headline,
        "concern_total": concern_total,
        "top_concern_total": len(concerns),
        "concern_limit": concern_limit,
        "signal_kinds": [str(signal.get("kind", "") or "") for signal in signals if isinstance(signal, dict)],
    }


def _empty_since_range_result(ref: str) -> dict[str, Any]:
    return {
        "mode": "code_review",
        "review_type": "since",
        "scores": {},
        "summary": {
            "headline": f"Unable to analyze changes since {ref}.",
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


def _result_from_report(
    report: dict[str, Any],
    *,
    review_type: str,
    since_ref: str = "",
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    duplicate_concerns = (
        near_duplicate_concerns(project_root)
        if review_type == "full" and project_root is not None
        else []
    )
    shadow_scan = _shadow_scan_for_review(
        report,
        review_type=review_type,
        project_root=project_root,
    )
    shadow_concerns = list(shadow_scan.get("concerns", []))
    generated_concerns = [
        *_cleanup_concerns(report),
        *_archive_concerns(report),
        *_hotspot_concerns(report),
        *_topology_concerns(report),
        *duplicate_concerns,
        *shadow_concerns,
    ]
    concerns = _ranked_concerns(generated_concerns, limit=CONCERN_LIMIT)
    signals = _signals(report, generated_concerns, shadow_scan=shadow_scan)
    return {
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
        ),
        "findings": [],
        "signals": signals,
        "evidence": _evidence(concerns),
        "concerns": concerns,
        "artifacts": _dict(report.get("artifacts")),
    }


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
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    report = run_analysis(
        project_root,
        goal="",
        diff=False,
        base="",
        head="",
        progress=progress,
    )
    result = _result_from_report(report, review_type="full", project_root=project_root)
    return _with_review_event(project_root, result)


def run_code_review_diff(
    project_root: str | Path,
    *,
    base: str = "",
    head: str = "",
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
    result = _result_from_report(report, review_type="diff", project_root=project_root)
    return _with_review_event(project_root, result)


def run_code_review_since(
    project_root: str | Path,
    *,
    ref: str,
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
    result = _result_from_report(report, review_type="since", since_ref=since_ref, project_root=project_root)
    return _with_review_event(project_root, result)


__all__ = [
    "run_code_review_diff",
    "run_code_review_full",
    "run_code_review_since",
]
