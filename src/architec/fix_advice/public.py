from __future__ import annotations

from pathlib import Path
from typing import Any

from architec.support.io_utils import read_json


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _location_path(concern: dict[str, Any]) -> str:
    location = _dict(concern.get("location"))
    return str(location.get("path", "") or "").strip()


def _matches_focus(
    concern: dict[str, Any],
    *,
    focus_file: str = "",
    focus_kind: str = "",
    concern_id: str = "",
) -> bool:
    if focus_file and focus_file not in _location_path(concern):
        return False
    if focus_kind and focus_kind != str(concern.get("kind", "") or ""):
        return False
    if concern_id and concern_id != str(concern.get("concern_id", "") or ""):
        return False
    return True


def _options_for_kind(kind: str, path: str) -> list[str]:
    if kind == "cleanup":
        return [
            f"Clarify ownership and retention intent for {path}.",
            "If the file is obsolete, plan a separate removal or archive change for human review.",
        ]
    if kind == "hotspot":
        return [
            f"Review whether new responsibility can be kept out of {path}.",
            "Consider splitting the next cohesive responsibility into a smaller module before adding more logic.",
        ]
    if kind == "boundary":
        return [
            f"Review package placement and dependency direction around {path}.",
            "Prefer moving behavior behind an existing boundary or facade instead of widening direct imports.",
        ]
    if kind == "missing-context":
        return [
            "Add the missing structured context to the source review or plan.",
            "Re-run the review before asking for more specific fix advice.",
        ]
    return [
        f"Review the evidence for {path or 'this concern'} and choose a local refactor direction.",
    ]


def _suggestion(concern: dict[str, Any]) -> dict[str, Any]:
    concern_id = str(concern.get("concern_id", "") or "")
    kind = str(concern.get("kind", "") or "unknown")
    path = _location_path(concern)
    evidence = [str(item) for item in _list(concern.get("evidence"))]
    if not evidence:
        return {
            "target": path,
            "concern": concern_id,
            "options": ["insufficient_evidence_for_fix_advice"],
            "tradeoffs": ["More precise advice needs concern evidence from the source review."],
            "risks": ["Acting without evidence may turn advisory output into guesswork."],
        }
    return {
        "target": path,
        "concern": concern_id,
        "options": _options_for_kind(kind, path),
        "tradeoffs": [
            "Keep the change small enough to verify independently.",
            "Prefer preserving existing public behavior unless a separate plan review covers the API change.",
        ],
        "risks": [
            "Advice is not executable code.",
            "Validate the chosen direction with code-review after implementation.",
        ],
    }


def _summary(suggestions: list[dict[str, Any]], *, filtered_total: int) -> dict[str, Any]:
    if not filtered_total:
        headline = "No fix advice suggestions were generated for this review."
    else:
        headline = "Fix advice generated from review concerns."
    return {
        "headline": headline,
        "suggestion_total": len(suggestions),
        "source_concern_total": filtered_total,
    }


def build_fix_advice(
    review: dict[str, Any],
    *,
    source_review: str = "",
    focus_file: str = "",
    focus_kind: str = "",
    concern_id: str = "",
) -> dict[str, Any]:
    concerns = [
        concern
        for concern in _list(review.get("concerns"))
        if isinstance(concern, dict)
        and _matches_focus(
            concern,
            focus_file=focus_file,
            focus_kind=focus_kind,
            concern_id=concern_id,
        )
    ]
    suggestions = [_suggestion(concern) for concern in concerns]
    return {
        "mode": "fix_advice",
        "source_review": source_review,
        "summary": _summary(suggestions, filtered_total=len(concerns)),
        "suggestions": suggestions,
        "artifacts": {},
    }


def run_fix_advice(
    review_path: str | Path,
    *,
    focus_file: str = "",
    focus_kind: str = "",
    concern_id: str = "",
) -> dict[str, Any]:
    path = Path(review_path)
    review = read_json(path, {})
    return build_fix_advice(
        _dict(review),
        source_review=str(path),
        focus_file=focus_file,
        focus_kind=focus_kind,
        concern_id=concern_id,
    )


__all__ = ["build_fix_advice", "run_fix_advice"]
