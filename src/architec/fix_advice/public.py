from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


LEGACY_COMPAT_TOKENS = {
    "backcompat",
    "compat",
    "compatibility",
    "deprecated",
    "deprecation",
    "legacy",
    "migrate",
    "migration",
    "shim",
}


class FixAdviceInputError(RuntimeError):
    """Raised when fix-advice cannot read a usable review JSON object."""


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


def _reference_from_structured(concern: dict[str, Any]) -> dict[str, Any]:
    for item in _list(concern.get("references")):
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "") or "") not in {"", "reference"}:
            continue
        path = str(item.get("path", "") or "").strip()
        if path:
            return {
                "path": path,
                "line": int(item.get("line", 0) or 0),
                "symbol": str(item.get("symbol", "") or "").strip(),
                "symbol_kind": str(item.get("symbol_kind", "") or "").strip(),
            }
    return {}


def _existing_implementation_reference(concern: dict[str, Any]) -> dict[str, Any]:
    for item in _list(concern.get("references")):
        if not isinstance(item, dict):
            continue
        if str(item.get("role", "") or "") != "existing_implementation":
            continue
        path = str(item.get("path", "") or "").strip()
        if path:
            return {
                "path": path,
                "line": int(item.get("line", 0) or 0),
                "symbol": str(item.get("symbol", "") or "").strip(),
                "symbol_kind": str(item.get("symbol_kind", "") or "").strip(),
            }
    return {}


def _reference_from_evidence(evidence: list[str]) -> dict[str, Any]:
    prefix = "near_duplicate.reference="
    for item in evidence:
        if not item.startswith(prefix):
            continue
        raw = item[len(prefix):]
        parts = raw.split(":", 2)
        if not parts or not parts[0].strip():
            continue
        line = 0
        if len(parts) >= 2:
            try:
                line = int(parts[1])
            except ValueError:
                line = 0
        return {
            "path": parts[0].strip(),
            "line": line,
            "symbol": parts[2].strip() if len(parts) >= 3 else "",
            "symbol_kind": "function",
        }
    return {}


def _shadow_reference_from_evidence(evidence: list[str]) -> dict[str, Any]:
    role_prefix = "shadow_implementation.existing="
    for item in evidence:
        if not item.startswith(role_prefix):
            continue
        raw = item[len(role_prefix):]
        parts = raw.split(":", 2)
        if not parts or not parts[0].strip():
            continue
        line = 0
        if len(parts) >= 2:
            try:
                line = int(parts[1])
            except ValueError:
                line = 0
        return {
            "path": parts[0].strip(),
            "line": line,
            "symbol": parts[2].strip() if len(parts) >= 3 else "",
            "symbol_kind": "",
        }
    return {}


def _evidence_value(evidence: list[str], key: str) -> str:
    prefix = f"{key}="
    for item in evidence:
        if item.startswith(prefix):
            return item[len(prefix):].strip()
    return ""


def _format_location(location: dict[str, Any]) -> str:
    path = str(location.get("path", "") or "").strip()
    symbol = str(location.get("symbol", "") or "").strip()
    line = int(location.get("line", 0) or 0)
    rendered = path or "this location"
    if line:
        rendered = f"{rendered}:{line}"
    if symbol:
        rendered = f"{rendered}:{symbol}"
    return rendered


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in re.split(r"[^A-Za-z0-9]+", text)
        if token
    }


def _has_legacy_compat_intent(concern: dict[str, Any], reference: dict[str, Any], evidence: list[str]) -> bool:
    location = _dict(concern.get("location"))
    fields = [
        str(location.get("path", "") or ""),
        str(location.get("symbol", "") or ""),
        str(reference.get("path", "") or ""),
        str(reference.get("symbol", "") or ""),
        *evidence,
    ]
    tokens: set[str] = set()
    for field in fields:
        tokens.update(_tokens(field))
    return bool(tokens & LEGACY_COMPAT_TOKENS)


def _duplication_suggestion(
    concern: dict[str, Any],
    *,
    concern_id: str,
    path: str,
    evidence: list[str],
) -> dict[str, Any]:
    location = _dict(concern.get("location"))
    duplicate = _format_location(location)
    reference = _reference_from_structured(concern) or _reference_from_evidence(evidence)
    if not reference:
        return {
            "target": path,
            "concern": concern_id,
            "options": [
                f"Review the near-duplicate implementation at {duplicate}.",
                "Identify the matching implementation before choosing reuse, extraction, or intentional divergence.",
            ],
            "tradeoffs": ["Evidence does not identify a reference implementation, so advice stays generic."],
            "risks": ["Merging duplicated code without a reference can preserve the wrong behavior."],
        }

    reference_text = _format_location(reference)
    options = [
        f"Compare duplicate {duplicate} with reference {reference_text}.",
        f"Consider routing the duplicate through the reference implementation at {reference_text} if behavior is intentionally shared.",
        "If the two implementations should diverge, document the difference near the duplicate or in its caller-facing contract.",
    ]
    if _has_legacy_compat_intent(concern, reference, evidence):
        options.append(
            "If the duplicate is a legacy or compatibility path, document that intent and keep the compatibility wrapper separate from the canonical implementation."
        )
    return {
        "target": path,
        "concern": concern_id,
        "options": options,
        "tradeoffs": [
            "Reusing the reference can reduce drift but may couple callers to one implementation boundary.",
            "Keeping both implementations can preserve local clarity when their behavior is expected to diverge.",
        ],
        "risks": [
            "Normalized AST similarity does not prove semantic equivalence.",
            "One implementation may contain a local bug or behavior that should not be copied.",
        ],
    }


def _architecture_contract_suggestion(
    concern: dict[str, Any],
    *,
    concern_id: str,
    path: str,
    evidence: list[str],
) -> dict[str, Any]:
    location = _dict(concern.get("location"))
    target = _format_location(location)
    rule_id = _evidence_value(evidence, "architecture_contract.rule_id")
    imported = _evidence_value(evidence, "architecture_contract.import")
    restricted = _evidence_value(evidence, "architecture_contract.restricted_import")
    owner = _evidence_value(evidence, "architecture_contract.owner")
    rule_text = f"rule {rule_id}" if rule_id else "the matched architecture contract"
    import_text = imported or restricted or "the matched import"
    options = [
        f"Compare {target} with {rule_text} for import {import_text}.",
        "Consider routing the dependency through the intended boundary or facade if the contract should stay in place.",
        "If the direct dependency is intentional, update the contract record or related plan with the reason for the exception.",
    ]
    hint = str(concern.get("next_steps_hint", "") or "").strip()
    if hint:
        options.append(f"Use the rule guidance as review context: {hint}")
    tradeoffs = [
        "Keeping the contract narrow can reduce boundary drift but may require a small adapter or facade change.",
        "Documenting an intentional exception can preserve local momentum but increases the contract surface maintainers must revisit.",
    ]
    if owner:
        tradeoffs.append(f"Coordinate the boundary decision with owner {owner}.")
    return {
        "target": path,
        "concern": concern_id,
        "options": options,
        "tradeoffs": tradeoffs,
        "risks": [
            "Import matching is static and may not capture runtime dependency direction.",
            "Advice does not decide whether the contract or the changed import is the better long-term boundary.",
        ],
    }


def _shadow_suggestion(
    concern: dict[str, Any],
    *,
    concern_id: str,
    path: str,
    evidence: list[str],
) -> dict[str, Any]:
    location = _dict(concern.get("location"))
    candidate = _format_location(location)
    reference = _existing_implementation_reference(concern) or _shadow_reference_from_evidence(evidence)
    if not reference:
        return {
            "target": path,
            "concern": concern_id,
            "options": [
                f"Review the shadow implementation concern at {candidate}.",
                "Identify the existing implementation before choosing reuse, extraction, or intentional divergence.",
            ],
            "tradeoffs": [
                "Evidence does not identify an existing implementation, so advice stays generic.",
            ],
            "risks": [
                "Similar role and structure do not prove one implementation should replace the other.",
            ],
        }

    reference_text = _format_location(reference)
    symbol_kind = str(location.get("symbol_kind", "") or reference.get("symbol_kind", "") or "")
    if symbol_kind == "class":
        options = [
            f"Compare class {candidate} with existing class {reference_text}.",
            f"Consider reusing {reference_text} or extracting shared behavior if both classes are meant to serve the same role.",
            "If the classes intentionally serve different contexts, document the divergence near the changed class or its callers.",
        ]
        tradeoffs = [
            "Reusing an existing class can reduce drift but may couple contexts that need different lifecycle or configuration behavior.",
            "Extracting shared behavior can clarify ownership, but it can also introduce an abstraction before the variation is stable.",
        ]
    else:
        options = [
            f"Compare {candidate} with existing implementation {reference_text}.",
            f"Consider routing through {reference_text} if the changed implementation should share behavior with the existing one.",
            "If both implementations should remain separate, document the intended difference in the changed implementation's local contract.",
        ]
        tradeoffs = [
            "Reusing the existing implementation can reduce drift but may require adapting callers to an existing boundary.",
            "Keeping separate implementations can preserve local behavior when the roles only appear similar.",
        ]
    return {
        "target": path,
        "concern": concern_id,
        "options": options,
        "tradeoffs": tradeoffs,
        "risks": [
            "Shadow implementation evidence is structural and role-based, not proof of semantic equivalence.",
            "Advice does not decide which implementation is correct.",
        ],
    }


def _suggestion(concern: dict[str, Any]) -> dict[str, Any]:
    concern_id = str(concern.get("concern_id", "") or "")
    kind = str(concern.get("kind", "") or "unknown")
    path = _location_path(concern)
    evidence = [str(item) for item in _list(concern.get("evidence"))]
    if kind == "duplication":
        return _duplication_suggestion(
            concern,
            concern_id=concern_id,
            path=path,
            evidence=evidence,
        )
    if kind == "shadow-implementation":
        return _shadow_suggestion(
            concern,
            concern_id=concern_id,
            path=path,
            evidence=evidence,
        )
    if kind == "architecture-contract" and evidence:
        return _architecture_contract_suggestion(
            concern,
            concern_id=concern_id,
            path=path,
            evidence=evidence,
        )
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
    summary = {
        "headline": headline,
        "suggestion_total": len(suggestions),
        "source_concern_total": filtered_total,
    }
    if not filtered_total:
        summary["reason"] = "The review has no matching concerns for the selected filters."
    return summary


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


def _read_review_json(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FixAdviceInputError(f"Review JSON not found: {path}") from exc
    except OSError as exc:
        raise FixAdviceInputError(f"Unable to read review JSON: {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FixAdviceInputError(f"Invalid review JSON: {path}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise FixAdviceInputError(f"Review JSON must be an object: {path}")
    return data


def run_fix_advice(
    review_path: str | Path,
    *,
    focus_file: str = "",
    focus_kind: str = "",
    concern_id: str = "",
) -> dict[str, Any]:
    path = Path(review_path)
    review = _read_review_json(path)
    return build_fix_advice(
        review,
        source_review=str(path),
        focus_file=focus_file,
        focus_kind=focus_kind,
        concern_id=concern_id,
    )


__all__ = ["FixAdviceInputError", "build_fix_advice", "run_fix_advice"]
