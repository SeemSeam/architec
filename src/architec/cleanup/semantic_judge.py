from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from architec.backend_llm import complete_json
from architec.cleanup.metadata import cleanup_metadata_fields, cleanup_metadata_text
from architec.integration.paths import (
    SEMANTIC_JUDGE_JSON_PATH,
    SEMANTIC_JUDGE_SUMMARY_MD_PATH,
)
from architec.support.io_utils import normalize_relpath, utc_now_iso, write_json
from architec.support.llm_guard import guard_llm_result

_SEMANTIC_JUDGE_NAMESPACE = "architect_semantic_judge"
_MAX_CANDIDATES = 10
_MAX_EXCERPT_CHARS = 280
_DECISION_ORDER = {
    "retire_now": 0,
    "archive_first": 1,
    "review": 2,
    "keep_active": 3,
}
_VALID_DECISIONS = frozenset(_DECISION_ORDER)


def load_cached_analysis(*args, **kwargs):
    from architec.analysis.analysis_cache import load_cached_analysis as impl

    return impl(*args, **kwargs)


def save_cached_analysis(*args, **kwargs):
    from architec.analysis.analysis_cache import save_cached_analysis as impl

    return impl(*args, **kwargs)


def _excerpt_text(root: Path, path: str) -> str:
    file_path = root / normalize_relpath(path)
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    collapsed = " ".join(str(text or "").split())
    return collapsed[:_MAX_EXCERPT_CHARS]


def _archive_items_by_path(archive_candidates: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_items = (
        archive_candidates.get("candidates", [])
        if isinstance(archive_candidates.get("candidates"), list)
        else []
    )
    out: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        path = normalize_relpath(str(item.get("path", "") or ""))
        if not path:
            continue
        out[path] = item
    return out


def semantic_judge_payload(
    project_root: str | Path,
    *,
    cleanup_inventory: dict[str, Any],
    archive_candidates: dict[str, Any],
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    archive_by_path = _archive_items_by_path(archive_candidates)
    raw_candidates = (
        cleanup_inventory.get("candidates", [])
        if isinstance(cleanup_inventory.get("candidates"), list)
        else []
    )
    candidates: list[dict[str, Any]] = []
    for item in raw_candidates[:_MAX_CANDIDATES]:
        if not isinstance(item, dict):
            continue
        path = normalize_relpath(str(item.get("path", "") or ""))
        if not path:
            continue
        archive_item = archive_by_path.get(path, {})
        candidates.append(
            {
                "path": path,
                "kind": str(item.get("kind", "") or ""),
                "category": str(item.get("category", "") or ""),
                "heuristic_confidence": round(float(item.get("confidence", 0.0) or 0.0), 2),
                "review_required": bool(item.get("review_required", False)),
                "evidence": item.get("evidence", [])[:4] if isinstance(item.get("evidence"), list) else [],
                "replacement": str(item.get("replacement", "") or "").strip(),
                "archive_tier": str(archive_item.get("archive_tier", "") or "").strip(),
                "archive_reason": str(archive_item.get("archive_reason", "") or "").strip(),
                "archive_path_hint": str(archive_item.get("archive_path_hint", "") or "").strip(),
                "excerpt": _excerpt_text(root, path),
                **cleanup_metadata_fields(item),
            }
        )
    cleanup_summary = {
        "candidate_total": int(cleanup_inventory.get("candidate_total", 0) or 0),
        "by_category": dict(
            sorted(
                (
                    Counter(
                        str(item.get("category", "") or "")
                        for item in raw_candidates
                        if isinstance(item, dict)
                    )
                ).items()
            )
        ),
    }
    archive_summary = {
        "candidate_total": int(archive_candidates.get("candidate_total", 0) or 0),
        "ready_total": int(archive_candidates.get("ready_total", 0) or 0),
        "review_total": int(archive_candidates.get("review_total", 0) or 0),
        "by_category": (
            archive_candidates.get("by_category", {})
            if isinstance(archive_candidates.get("by_category"), dict)
            else {}
        ),
    }
    return {
        "cleanup_summary": cleanup_summary,
        "archive_summary": archive_summary,
        "candidates": candidates,
    }


def _llm_semantic_judge(
    root: Path,
    payload: dict[str, Any],
    *,
    fail_open: bool,
) -> dict[str, Any] | None:
    prompt = f"Input:\n{payload}"
    return guard_llm_result(
        root,
        task=_SEMANTIC_JUDGE_NAMESPACE,
        fail_open=fail_open,
        runner=lambda: complete_json(
            root,
            task=_SEMANTIC_JUDGE_NAMESPACE,
            tier="strong",
            prompt=prompt,
            timeout_sec=25.0,
            max_tokens=2600,
            required=True,
        ),
    )


def _normalized_decision(raw: object, *, kind: str) -> str:
    decision = str(raw or "").strip().lower()
    if decision not in _VALID_DECISIONS:
        return "review"
    if decision == "archive_first" and kind == "source":
        return "review"
    return decision


def _fallback_summary(
    *,
    judgments: list[dict[str, Any]],
    candidate_pool_total: int,
) -> str:
    if not judgments:
        return "Semantic judge returned no actionable judgments."
    by_decision = Counter(str(item.get("decision", "") or "") for item in judgments)
    rendered = ", ".join(f"{name}={value}" for name, value in sorted(by_decision.items()))
    return f"Reviewed {len(judgments)} of {candidate_pool_total} candidates. Decisions: {rendered}."


def _normalized_unavailable(
    raw: dict[str, Any],
    *,
    candidate_pool_total: int,
    status: str,
) -> dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "status": status,
        "candidate_pool_total": candidate_pool_total,
        "reviewed_total": 0,
        "by_decision": {},
        "summary": str(raw.get("error", "") or raw.get("summary", "") or "").strip(),
        "top_judgments": [],
        "judgments": [],
        "cache_hit": bool(raw.get("_cache_hit", False)),
        "error_type": str(raw.get("error_type", "") or "").strip(),
        "error": str(raw.get("error", "") or "").strip(),
    }


def _judgment_item(
    raw: dict[str, Any],
    *,
    source: dict[str, Any],
) -> dict[str, Any]:
    decision = _normalized_decision(raw.get("decision"), kind=str(source.get("kind", "") or ""))
    replacement = str(raw.get("replacement", "") or source.get("replacement", "") or "").strip()
    archive_path_hint = str(
        raw.get("archive_path_hint", "") or source.get("archive_path_hint", "") or ""
    ).strip()
    signals = raw.get("signals", [])
    return {
        "path": str(source.get("path", "") or ""),
        "kind": str(source.get("kind", "") or ""),
        "category": str(source.get("category", "") or ""),
        "heuristic_confidence": round(float(source.get("heuristic_confidence", 0.0) or 0.0), 2),
        "decision": decision,
        "confidence": round(float(raw.get("confidence", 0.0) or 0.0), 2),
        "reason": str(raw.get("reason", "") or "").strip(),
        "replacement": replacement,
        "archive_tier": str(source.get("archive_tier", "") or ""),
        "archive_path_hint": archive_path_hint,
        "evidence": source.get("evidence", []) if isinstance(source.get("evidence"), list) else [],
        "signals": [str(item or "") for item in signals[:4]] if isinstance(signals, list) else [],
        **cleanup_metadata_fields(source),
    }


def _normalized_semantic_judge(
    raw: dict[str, Any] | None,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    candidate_pool = payload.get("candidates", []) if isinstance(payload.get("candidates"), list) else []
    candidate_pool_total = len(candidate_pool)
    if not isinstance(raw, dict):
        return _normalized_unavailable({}, candidate_pool_total=candidate_pool_total, status="unavailable")
    status = str(raw.get("status", "") or "ok").strip().lower()
    if status in {"unavailable", "skipped"}:
        return _normalized_unavailable(raw, candidate_pool_total=candidate_pool_total, status=status)

    by_path = {
        str(item.get("path", "") or ""): item
        for item in candidate_pool
        if isinstance(item, dict) and str(item.get("path", "") or "")
    }
    judgments_raw = raw.get("judgments", []) if isinstance(raw.get("judgments"), list) else []
    judgments: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in judgments_raw:
        if not isinstance(item, dict):
            continue
        path = normalize_relpath(str(item.get("path", "") or ""))
        source = by_path.get(path)
        if source is None or path in seen:
            continue
        seen.add(path)
        judgments.append(_judgment_item(item, source=source))

    judgments.sort(
        key=lambda item: (
            _DECISION_ORDER.get(str(item.get("decision", "") or ""), 99),
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("path", "") or ""),
        )
    )
    by_decision = Counter(str(item.get("decision", "") or "") for item in judgments)
    return {
        "generated_at": utc_now_iso(),
        "status": "ok",
        "candidate_pool_total": candidate_pool_total,
        "reviewed_total": len(judgments),
        "by_decision": dict(sorted(by_decision.items())),
        "summary": str(raw.get("summary", "") or "").strip()
        or _fallback_summary(judgments=judgments, candidate_pool_total=candidate_pool_total),
        "top_judgments": judgments[:8],
        "judgments": judgments,
        "cache_hit": bool(raw.get("_cache_hit", False)),
    }


def run_semantic_judge(
    project_root: str | Path,
    *,
    cleanup_inventory: dict[str, Any],
    archive_candidates: dict[str, Any],
    llm_enabled: bool = True,
    fail_open: bool = True,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    payload = semantic_judge_payload(
        root,
        cleanup_inventory=cleanup_inventory,
        archive_candidates=archive_candidates,
    )
    candidate_pool = payload.get("candidates", []) if isinstance(payload.get("candidates"), list) else []
    candidate_pool_total = len(candidate_pool)
    if candidate_pool_total <= 0:
        return {
            "generated_at": utc_now_iso(),
            "status": "skipped",
            "candidate_pool_total": 0,
            "reviewed_total": 0,
            "by_decision": {},
            "summary": "No cleanup candidates available for semantic review.",
            "top_judgments": [],
            "judgments": [],
            "cache_hit": False,
        }
    if not llm_enabled:
        return {
            "generated_at": utc_now_iso(),
            "status": "skipped",
            "candidate_pool_total": candidate_pool_total,
            "reviewed_total": 0,
            "by_decision": {},
            "summary": "Semantic judge skipped because LLM enhancement is disabled for this command path.",
            "top_judgments": [],
            "judgments": [],
            "cache_hit": False,
        }

    cached = load_cached_analysis(
        root,
        namespace=_SEMANTIC_JUDGE_NAMESPACE,
        payload=payload,
    )
    if isinstance(cached, dict) and str(cached.get("status", "") or "ok").strip().lower() == "ok":
        return _normalized_semantic_judge(cached, payload=payload)

    raw = _llm_semantic_judge(root, payload, fail_open=fail_open)
    if isinstance(raw, dict) and str(raw.get("status", "") or "ok").strip().lower() == "ok":
        save_cached_analysis(
            root,
            namespace=_SEMANTIC_JUDGE_NAMESPACE,
            payload=payload,
            result=raw,
        )
    return _normalized_semantic_judge(raw, payload=payload)


def semantic_judge_report_view(semantic_judge: dict[str, Any]) -> dict[str, Any]:
    out = {
        "status": str(semantic_judge.get("status", "") or "skipped"),
        "candidate_pool_total": int(semantic_judge.get("candidate_pool_total", 0) or 0),
        "reviewed_total": int(semantic_judge.get("reviewed_total", 0) or 0),
        "by_decision": (
            semantic_judge.get("by_decision", {})
            if isinstance(semantic_judge.get("by_decision"), dict)
            else {}
        ),
        "summary": str(semantic_judge.get("summary", "") or "").strip(),
        "top_judgments": [
            item
            for item in (
                semantic_judge.get("top_judgments", [])
                if isinstance(semantic_judge.get("top_judgments"), list)
                else []
            )[:8]
            if isinstance(item, dict)
        ],
    }
    error = str(semantic_judge.get("error", "") or "").strip()
    if error:
        out["error"] = error
    return out


def render_semantic_judge_summary(semantic_judge: dict[str, Any]) -> str:
    status = str(semantic_judge.get("status", "") or "skipped")
    lines = [
        "# Semantic Judge Summary",
        "",
        f"Status: {status}",
        f"Candidate pool: {int(semantic_judge.get('candidate_pool_total', 0) or 0)}",
        f"Reviewed: {int(semantic_judge.get('reviewed_total', 0) or 0)}",
    ]
    by_decision = (
        semantic_judge.get("by_decision", {})
        if isinstance(semantic_judge.get("by_decision"), dict)
        else {}
    )
    if by_decision:
        lines.append(
            "Decisions: " + ", ".join(f"{name}={value}" for name, value in by_decision.items())
        )
    summary = str(semantic_judge.get("summary", "") or "").strip()
    if summary:
        lines.append(f"Summary: {summary}")
    lines.extend(["", "## Top Judgments", ""])
    if status != "ok":
        error = str(semantic_judge.get("error", "") or "").strip()
        if error:
            lines.append(f"- Semantic judge unavailable: {error}")
        else:
            lines.append("- Semantic judge did not produce actionable judgments for this run.")
        return "\n".join(lines) + "\n"
    judgments = (
        semantic_judge.get("judgments", [])
        if isinstance(semantic_judge.get("judgments"), list)
        else []
    )
    if not judgments:
        lines.append("- No semantic judgments returned.")
        return "\n".join(lines) + "\n"
    for item in judgments[:12]:
        if not isinstance(item, dict):
            continue
        line = (
            f"- `{item.get('path', '')}` -> {item.get('decision', '')} "
            f"({float(item.get('confidence', 0.0) or 0.0):.2f})"
        )
        reason = str(item.get("reason", "") or "").strip()
        replacement = str(item.get("replacement", "") or "").strip()
        archive_path_hint = str(item.get("archive_path_hint", "") or "").strip()
        if reason:
            line += f" | {reason}"
        if replacement:
            line += f" | replace with `{replacement}`"
        if archive_path_hint:
            line += f" | archive as `{archive_path_hint}`"
        metadata_text = cleanup_metadata_text(item)
        if metadata_text:
            line += f" | {metadata_text}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def write_semantic_judge_artifacts(
    project_root: str | Path,
    *,
    semantic_judge: dict[str, Any],
) -> dict[str, str]:
    root = Path(project_root).resolve()
    json_path = root / SEMANTIC_JUDGE_JSON_PATH
    summary_path = root / SEMANTIC_JUDGE_SUMMARY_MD_PATH
    write_json(json_path, semantic_judge)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_semantic_judge_summary(semantic_judge), encoding="utf-8")
    return {
        "semantic_judge_json": str(json_path),
        "semantic_judge_summary_md": str(summary_path),
    }


__all__ = [
    "render_semantic_judge_summary",
    "run_semantic_judge",
    "semantic_judge_payload",
    "semantic_judge_report_view",
    "write_semantic_judge_artifacts",
]
