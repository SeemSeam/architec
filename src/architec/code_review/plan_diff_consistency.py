from __future__ import annotations

import hashlib
import json
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any

from architec.code_review.python_imports import import_records, module_matches
from architec.support.io_utils import normalize_relpath


ALTERNATIVE_IMPORT_KEYS = ("any_of", "alternatives", "alternative_imports")
SEMANTIC_ALL_TERM_KEYS = ("required_terms", "requires_terms", "all_of", "must_include")
SEMANTIC_ANY_TERM_KEYS = ("any_of_terms", "requires_any", "any_of")
SEMANTIC_FORBIDDEN_TERM_KEYS = ("forbidden_terms", "must_not_include", "disallowed_terms")


def _normal_path(path: object) -> str:
    text = normalize_relpath(str(path or ""))
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _planned_paths(plan_review: dict[str, Any]) -> list[str]:
    understood = plan_review.get("understood_plan")
    if not isinstance(understood, dict):
        return []
    raw_changes = understood.get("changes")
    if not isinstance(raw_changes, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw_changes:
        path = ""
        if isinstance(item, dict):
            path = _normal_path(item.get("path", ""))
        else:
            path = _normal_path(item)
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, list) else [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _dependency_source(item: dict[str, Any]) -> str:
    for key in ("source_glob", "source", "path", "from_path"):
        text = _normal_path(item.get(key, ""))
        if text:
            return text
    return ""


def _dependency_imports(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("imports", "modules", "module", "import", "target", "dependency"):
        values.extend(_string_list(item.get(key)))
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _dependency_alternative_imports(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ALTERNATIVE_IMPORT_KEYS:
        raw = item.get(key)
        entries = raw if isinstance(raw, list) else [raw]
        values.extend(str(entry).strip() for entry in entries if isinstance(entry, str) and entry.strip())
    out: list[str] = []
    seen: set[str] = set()
    for value in sorted(values):
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _test_expectation_path(item: dict[str, Any]) -> str:
    for key in ("test_path", "test_glob", "path", "glob", "test"):
        text = _normal_path(item.get(key, ""))
        if text:
            return text
    return ""


def _test_expectation_source(item: dict[str, Any]) -> str:
    for key in ("source_glob", "source", "source_path", "source_path_glob", "for_path", "from_path"):
        text = _normal_path(item.get(key, ""))
        if text:
            return text
    return ""


def _public_api_migration_path(item: dict[str, Any]) -> str:
    for key in ("path", "api_path", "public_api_path", "glob", "api_glob"):
        text = _normal_path(item.get(key, ""))
        if text:
            return text
    return ""


def _public_api_migration_source(item: dict[str, Any]) -> str:
    for key in ("source_glob", "source", "from_path"):
        text = _normal_path(item.get(key, ""))
        if text:
            return text
    return ""


def _context_value(item: dict[str, Any], key: str) -> str:
    return str(item.get(key, "") or "").strip()


def _structured_string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _semantic_source(item: dict[str, Any]) -> str:
    for key in ("source_glob", "source", "path", "path_glob", "for_path", "from_path"):
        text = _normal_path(item.get(key, ""))
        if text:
            return text
    return ""


def _semantic_terms(item: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = item.get(key)
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, list):
            values.extend(entry for entry in raw if isinstance(entry, str))
    out: list[str] = []
    seen: set[str] = set()
    for value in sorted(text.strip() for text in values if text.strip()):
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _planned_import_expectations(plan_review: dict[str, Any]) -> list[dict[str, Any]]:
    understood = plan_review.get("understood_plan")
    if not isinstance(understood, dict):
        return []
    raw_dependencies = understood.get("dependencies")
    if not isinstance(raw_dependencies, list):
        return []
    expectations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    seen_alternatives: set[tuple[str, tuple[str, ...]]] = set()
    for item in raw_dependencies:
        if not isinstance(item, dict):
            continue
        source = _dependency_source(item)
        imports = _dependency_imports(item)
        for module in imports:
            key = (source, module)
            if key in seen:
                continue
            seen.add(key)
            expectations.append({"source": source, "module": module})
        alternatives = _dependency_alternative_imports(item)
        if len(alternatives) == 1:
            module = alternatives[0]
            key = (source, module)
            if key not in seen:
                seen.add(key)
                expectations.append({"source": source, "module": module})
        elif len(alternatives) > 1:
            alt_key = (source, tuple(alternatives))
            if alt_key in seen_alternatives:
                continue
            seen_alternatives.add(alt_key)
            expectations.append({"source": source, "modules": alternatives, "alternative": True})
    return expectations


def _planned_public_api_migrations(plan_review: dict[str, Any]) -> list[dict[str, Any]]:
    understood = plan_review.get("understood_plan")
    if not isinstance(understood, dict):
        return []
    expectations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for field in ("public_api_migrations", "api_migrations"):
        raw_migrations = understood.get(field)
        if not isinstance(raw_migrations, list):
            continue
        for item in raw_migrations:
            if not isinstance(item, dict):
                continue
            path = _public_api_migration_path(item)
            if not path:
                continue
            source = _public_api_migration_source(item)
            symbol = _context_value(item, "symbol")
            old_symbol = _context_value(item, "old_symbol")
            new_symbol = _context_value(item, "new_symbol")
            key = (source, path, symbol, old_symbol, new_symbol)
            if key in seen:
                continue
            seen.add(key)
            expectations.append(
                {
                    "source": source,
                    "path": path,
                    "symbol": symbol,
                    "old_symbol": old_symbol,
                    "new_symbol": new_symbol,
                }
            )
    return expectations


def _planned_test_expectations(plan_review: dict[str, Any]) -> list[dict[str, Any]]:
    understood = plan_review.get("understood_plan")
    if not isinstance(understood, dict):
        return []
    expectations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for field in ("expected_tests", "tests"):
        raw_tests = understood.get(field)
        if not isinstance(raw_tests, list):
            continue
        for item in raw_tests:
            if not isinstance(item, dict):
                continue
            test_path = _test_expectation_path(item)
            if not test_path:
                continue
            source = _test_expectation_source(item)
            key = (source, test_path)
            if key in seen:
                continue
            seen.add(key)
            expectations.append({"source": source, "test_path": test_path})
    return expectations


def _planned_semantic_intents(plan_review: dict[str, Any]) -> list[dict[str, Any]]:
    understood = plan_review.get("understood_plan")
    if not isinstance(understood, dict):
        return []
    expectations: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...], str, str, str]] = set()
    for field in ("intent_checks", "semantic_intents"):
        raw_entries = understood.get(field)
        if not isinstance(raw_entries, list):
            continue
        for item in raw_entries:
            if not isinstance(item, dict):
                continue
            all_terms = _semantic_terms(item, SEMANTIC_ALL_TERM_KEYS)
            any_terms = _semantic_terms(item, SEMANTIC_ANY_TERM_KEYS)
            forbidden_terms = _semantic_terms(item, SEMANTIC_FORBIDDEN_TERM_KEYS)
            if not all_terms and not any_terms and not forbidden_terms:
                continue
            source = _semantic_source(item)
            label = _structured_string(item.get("label"))
            intent = _structured_string(item.get("intent"))
            reason = _structured_string(item.get("reason"))
            key = (
                source,
                tuple(all_terms),
                tuple(any_terms),
                tuple(forbidden_terms),
                label,
                intent,
                reason,
            )
            if key in seen:
                continue
            seen.add(key)
            expectations.append(
                {
                    "source": source,
                    "all_terms": all_terms,
                    "any_terms": any_terms,
                    "forbidden_terms": forbidden_terms,
                    "label": label,
                    "intent": intent,
                    "reason": reason,
                }
            )
    return expectations


def _path_matches(path: str, pattern: str) -> bool:
    normalized = _normal_path(path)
    planned = _normal_path(pattern)
    if not normalized or not planned:
        return False
    if "*" in planned or "?" in planned or "[" in planned:
        return fnmatchcase(normalized, planned) or PurePosixPath(normalized).match(planned)
    return normalized == planned or normalized.startswith(f"{planned.rstrip('/')}/")


def _stable_concern_id(kind: str, *, path: str, plan_path: str, plan_fingerprint: str) -> str:
    payload = {
        "kind": kind,
        "path": path,
        "plan_path": plan_path,
        "plan_fingerprint": plan_fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:{kind}:{digest}"


def _stable_import_concern_id(
    *,
    source: str,
    module: str,
    plan_path: str,
    plan_fingerprint: str,
) -> str:
    payload = {
        "kind": "plan-diff-consistency",
        "observation": "planned_import_not_observed",
        "source": source,
        "module": module,
        "plan_path": plan_path,
        "plan_fingerprint": plan_fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:plan-diff-consistency:{digest}"


def _stable_import_alternative_concern_id(
    *,
    source: str,
    modules: list[str],
    plan_path: str,
    plan_fingerprint: str,
) -> str:
    payload = {
        "kind": "plan-diff-consistency",
        "observation": "planned_import_alternative_not_observed",
        "source": source,
        "modules": sorted(modules),
        "plan_path": plan_path,
        "plan_fingerprint": plan_fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:plan-diff-consistency:{digest}"


def _stable_test_concern_id(
    *,
    source: str,
    test_path: str,
    plan_path: str,
    plan_fingerprint: str,
) -> str:
    payload = {
        "kind": "plan-diff-consistency",
        "observation": "planned_test_not_observed",
        "source": source,
        "test_path": test_path,
        "plan_path": plan_path,
        "plan_fingerprint": plan_fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:plan-diff-consistency:{digest}"


def _stable_public_api_migration_concern_id(
    *,
    source: str,
    path: str,
    symbol: str,
    old_symbol: str,
    new_symbol: str,
    plan_path: str,
    plan_fingerprint: str,
) -> str:
    payload = {
        "kind": "plan-diff-consistency",
        "observation": "planned_public_api_migration_not_observed",
        "source": source,
        "path": path,
        "symbol": symbol,
        "old_symbol": old_symbol,
        "new_symbol": new_symbol,
        "plan_path": plan_path,
        "plan_fingerprint": plan_fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:plan-diff-consistency:{digest}"


def _stable_semantic_intent_concern_id(
    *,
    observation: str,
    expectation: dict[str, Any],
    plan_path: str,
    plan_fingerprint: str,
) -> str:
    payload = {
        "kind": "plan-diff-consistency",
        "observation": observation,
        "source": str(expectation.get("source", "") or ""),
        "all_terms": list(_string_list(expectation.get("all_terms"))),
        "any_terms": list(_string_list(expectation.get("any_terms"))),
        "forbidden_terms": list(_string_list(expectation.get("forbidden_terms"))),
        "label": str(expectation.get("label", "") or ""),
        "intent": str(expectation.get("intent", "") or ""),
        "reason": str(expectation.get("reason", "") or ""),
        "plan_path": plan_path,
        "plan_fingerprint": plan_fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:plan-diff-consistency:{digest}"


def _unexpected_change_concern(
    *,
    path: str,
    planned_paths: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    evidence = [
        "plan_diff_consistency.observation=unexpected_changed_file",
        f"plan_diff_consistency.changed_file={path}",
        f"plan_diff_consistency.planned_path_total={len(planned_paths)}",
    ]
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    return {
        "concern_id": _stable_concern_id(
            "plan-diff-consistency",
            path=path,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "caution",
        "confidence": 0.8,
        "location": {
            "path": path,
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "Changed file is outside the saved plan-review touchpoints.",
        "evidence": evidence,
        "blast_radius": [path],
        "next_steps_hint": "Review whether the plan artifact should include this touchpoint or whether the change should be narrowed.",
    }


def _missing_planned_path_concern(
    *,
    path: str,
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    evidence = [
        "plan_diff_consistency.observation=planned_path_not_changed",
        f"plan_diff_consistency.planned_path={path}",
        f"plan_diff_consistency.changed_file_total={len(changed_files)}",
    ]
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    return {
        "concern_id": _stable_concern_id(
            "plan-diff-consistency",
            path=path,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "info",
        "confidence": 0.75,
        "location": {
            "path": path,
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "Saved plan-review touchpoint is not present in the selected diff.",
        "evidence": evidence,
        "blast_radius": [path],
        "next_steps_hint": "Review whether the plan is partially implemented or whether this touchpoint is no longer needed.",
    }


def _missing_planned_import_concern(
    *,
    source: str,
    module: str,
    changed_files: list[str],
    scoped_changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    location_path = scoped_changed_files[0] if scoped_changed_files else source or plan_path or "plan-review"
    evidence = [
        "plan_diff_consistency.observation=planned_import_not_observed",
        f"plan_diff_consistency.planned_import={module}",
        f"plan_diff_consistency.changed_file_total={len(changed_files)}",
        f"plan_diff_consistency.scoped_changed_file_total={len(scoped_changed_files)}",
    ]
    if source:
        evidence.append(f"plan_diff_consistency.dependency_source={source}")
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    return {
        "concern_id": _stable_import_concern_id(
            source=source,
            module=module,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "info",
        "confidence": 0.7,
        "location": {
            "path": location_path,
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "Saved plan-review dependency was not observed in the selected diff imports.",
        "evidence": evidence,
        "blast_radius": [path for path in (source, *scoped_changed_files) if path],
        "next_steps_hint": "Review whether the dependency expectation is still intended or whether the implementation uses a different boundary.",
    }


def _missing_planned_import_alternative_concern(
    *,
    source: str,
    modules: list[str],
    changed_files: list[str],
    scoped_changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    location_path = scoped_changed_files[0] if scoped_changed_files else source or plan_path or "plan-review"
    candidates = ",".join(sorted(modules))
    evidence = [
        "plan_diff_consistency.observation=planned_import_alternative_not_observed",
        f"plan_diff_consistency.planned_import_alternatives={candidates}",
        f"plan_diff_consistency.planned_import_alternative_total={len(modules)}",
        f"plan_diff_consistency.changed_file_total={len(changed_files)}",
        f"plan_diff_consistency.scoped_changed_file_total={len(scoped_changed_files)}",
    ]
    if source:
        evidence.append(f"plan_diff_consistency.dependency_source={source}")
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    return {
        "concern_id": _stable_import_alternative_concern_id(
            source=source,
            modules=modules,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "info",
        "confidence": 0.7,
        "location": {
            "path": location_path,
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "Saved plan-review dependency alternatives were not observed in the selected diff imports.",
        "evidence": evidence,
        "blast_radius": [path for path in (source, *scoped_changed_files) if path],
        "next_steps_hint": "Review whether one of the dependency alternatives is still intended or whether the implementation uses a different boundary.",
    }


def _missing_planned_test_concern(
    *,
    source: str,
    test_path: str,
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    evidence = [
        "plan_diff_consistency.observation=planned_test_not_observed",
        f"plan_diff_consistency.expected_test={test_path}",
        f"plan_diff_consistency.changed_file_total={len(changed_files)}",
    ]
    if source:
        evidence.append(f"plan_diff_consistency.test_source={source}")
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    location_path = test_path or source or plan_path or "plan-review"
    return {
        "concern_id": _stable_test_concern_id(
            source=source,
            test_path=test_path,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "info",
        "confidence": 0.72,
        "location": {
            "path": location_path,
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "Saved plan-review expected test path was not observed in the selected diff.",
        "evidence": evidence,
        "blast_radius": [path for path in (source, test_path) if path],
        "next_steps_hint": "Review whether the expected test change is still intended or whether the plan-review artifact should be updated.",
    }


def _missing_public_api_migration_concern(
    *,
    expectation: dict[str, Any],
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    source = _normal_path(expectation.get("source", ""))
    path = _normal_path(expectation.get("path", ""))
    symbol = str(expectation.get("symbol", "") or "").strip()
    old_symbol = str(expectation.get("old_symbol", "") or "").strip()
    new_symbol = str(expectation.get("new_symbol", "") or "").strip()
    evidence = [
        "plan_diff_consistency.observation=planned_public_api_migration_not_observed",
        f"plan_diff_consistency.public_api_migration={path}",
        f"plan_diff_consistency.changed_file_total={len(changed_files)}",
    ]
    if source:
        evidence.append(f"plan_diff_consistency.migration_source={source}")
    if symbol:
        evidence.append(f"plan_diff_consistency.symbol={symbol}")
    if old_symbol:
        evidence.append(f"plan_diff_consistency.old_symbol={old_symbol}")
    if new_symbol:
        evidence.append(f"plan_diff_consistency.new_symbol={new_symbol}")
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    return {
        "concern_id": _stable_public_api_migration_concern_id(
            source=source,
            path=path,
            symbol=symbol,
            old_symbol=old_symbol,
            new_symbol=new_symbol,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "info",
        "confidence": 0.72,
        "location": {
            "path": path or source or plan_path or "plan-review",
            "line": 0,
            "symbol": symbol or new_symbol or old_symbol,
            "symbol_kind": "module",
        },
        "root_cause": "Saved plan-review public API migration touchpoint was not observed in the selected diff.",
        "evidence": evidence,
        "blast_radius": [item for item in (source, path) if item],
        "next_steps_hint": "Review whether the public API migration is still intended or whether the plan-review artifact should be updated.",
    }


def _semantic_context_value(expectation: dict[str, Any]) -> str:
    for key in ("label", "intent", "reason"):
        text = str(expectation.get(key, "") or "").strip()
        if text:
            return text
    return ""


def _term_summary(terms: list[str]) -> str:
    return ",".join(terms)


def _semantic_intent_concern(
    *,
    observation: str,
    expectation: dict[str, Any],
    scoped_changed_files: list[str],
    changed_files: list[str],
    missing_all_terms: list[str],
    missing_any_terms: list[str],
    observed_forbidden_terms: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> dict[str, Any]:
    source = _normal_path(expectation.get("source", ""))
    all_terms = _string_list(expectation.get("all_terms"))
    any_terms = _string_list(expectation.get("any_terms"))
    forbidden_terms = _string_list(expectation.get("forbidden_terms"))
    evidence = [
        f"plan_diff_consistency.observation={observation}",
        f"plan_diff_consistency.changed_file_total={len(changed_files)}",
        f"plan_diff_consistency.scoped_changed_file_total={len(scoped_changed_files)}",
    ]
    label = _semantic_context_value(expectation)
    if label:
        evidence.append(f"plan_diff_consistency.intent_label={label}")
    if source:
        evidence.append(f"plan_diff_consistency.intent_source={source}")
    if all_terms:
        evidence.append(f"plan_diff_consistency.required_term_total={len(all_terms)}")
        evidence.append(f"plan_diff_consistency.required_terms={_term_summary(all_terms)}")
    if any_terms:
        evidence.append(f"plan_diff_consistency.any_term_total={len(any_terms)}")
        evidence.append(f"plan_diff_consistency.any_terms={_term_summary(any_terms)}")
    if forbidden_terms:
        evidence.append(f"plan_diff_consistency.forbidden_term_total={len(forbidden_terms)}")
        evidence.append(f"plan_diff_consistency.forbidden_terms={_term_summary(forbidden_terms)}")
    if missing_all_terms:
        evidence.append(f"plan_diff_consistency.missing_required_terms={_term_summary(missing_all_terms)}")
    if missing_any_terms:
        evidence.append(f"plan_diff_consistency.missing_any_terms={_term_summary(missing_any_terms)}")
    if observed_forbidden_terms:
        evidence.append(f"plan_diff_consistency.observed_forbidden_terms={_term_summary(observed_forbidden_terms)}")
    if plan_fingerprint:
        evidence.append(f"plan_diff_consistency.plan_fingerprint={plan_fingerprint}")
    if plan_path:
        evidence.append(f"plan_diff_consistency.plan_path={plan_path}")
    location_path = scoped_changed_files[0]
    return {
        "concern_id": _stable_semantic_intent_concern_id(
            observation=observation,
            expectation=expectation,
            plan_path=plan_path,
            plan_fingerprint=plan_fingerprint,
        ),
        "kind": "plan-diff-consistency",
        "level": "info",
        "confidence": 0.7,
        "location": {
            "path": location_path,
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "Saved plan-review semantic intent terms were not matched in the selected diff.",
        "evidence": evidence,
        "blast_radius": scoped_changed_files,
        "next_steps_hint": "Review whether the saved semantic intent remains applicable or whether the plan-review artifact should be updated.",
    }


def load_plan_review(path: str | Path) -> dict[str, Any]:
    review_path = Path(path)
    try:
        loaded = json.loads(review_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Plan-review JSON not found: {review_path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid plan-review JSON: {review_path}: {exc.msg}") from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to read plan-review JSON: {review_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise RuntimeError(f"Plan-review JSON must be an object: {review_path}")
    return loaded


def _imports_by_changed_file(project_root: Path | None, changed_files: list[str]) -> dict[str, list[str]]:
    if project_root is None:
        return {}
    imports_by_file: dict[str, list[str]] = {}
    for path in changed_files:
        target = project_root / path
        if target.suffix != ".py" or not target.exists():
            continue
        try:
            source = target.read_text(encoding="utf-8")
        except OSError:
            continue
        modules: list[str] = []
        seen: set[str] = set()
        for record in import_records(path, source):
            if record.module in seen:
                continue
            seen.add(record.module)
            modules.append(record.module)
        imports_by_file[path] = modules
    return imports_by_file


def _text_by_changed_file(project_root: Path | None, changed_files: list[str]) -> dict[str, str]:
    if project_root is None:
        return {}
    text_by_file: dict[str, str] = {}
    for path in changed_files:
        target = project_root / path
        if not target.exists() or not target.is_file():
            continue
        try:
            text_by_file[path] = target.read_text(encoding="utf-8").lower()
        except (OSError, UnicodeDecodeError):
            continue
    return text_by_file


def _scoped_changed_files(changed_files: list[str], source: str) -> list[str]:
    if not source:
        return changed_files
    return [path for path in changed_files if _path_matches(path, source)]


def _import_expectation_modules(expectation: dict[str, Any]) -> list[str]:
    if bool(expectation.get("alternative")):
        return [str(module or "").strip() for module in _string_list(expectation.get("modules")) if str(module or "").strip()]
    module = str(expectation.get("module", "") or "").strip()
    return [module] if module else []


def _import_expectation_scan(
    *,
    expectations: list[dict[str, Any]],
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
    project_root: Path | None,
) -> dict[str, Any]:
    if not expectations or project_root is None:
        return {"concerns": [], "observed_import_total": 0, "missing_import_total": 0}
    imports_by_file = _imports_by_changed_file(project_root, changed_files)
    changed_python_files = list(imports_by_file)
    concerns: list[dict[str, Any]] = []
    observed_total = 0
    missing_total = 0
    for expectation in expectations:
        source = _normal_path(expectation.get("source", ""))
        modules = _import_expectation_modules(expectation)
        if not modules:
            continue
        scoped_files = _scoped_changed_files(changed_python_files, source)
        if not scoped_files:
            continue
        observed = any(
            module_matches(imported, module)
            for module in modules
            for path in scoped_files
            for imported in imports_by_file.get(path, [])
        )
        if observed:
            observed_total += 1
            continue
        missing_total += 1
        if bool(expectation.get("alternative")):
            concerns.append(
                _missing_planned_import_alternative_concern(
                    source=source,
                    modules=modules,
                    changed_files=changed_files,
                    scoped_changed_files=scoped_files,
                    plan_fingerprint=plan_fingerprint,
                    plan_path=plan_path,
                )
            )
        else:
            concerns.append(
                _missing_planned_import_concern(
                    source=source,
                    module=modules[0],
                    changed_files=changed_files,
                    scoped_changed_files=scoped_files,
                    plan_fingerprint=plan_fingerprint,
                    plan_path=plan_path,
                )
            )
    return {
        "concerns": concerns,
        "observed_import_total": observed_total,
        "missing_import_total": missing_total,
    }


def _test_expectation_concerns(
    *,
    plan_review: dict[str, Any],
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> list[dict[str, Any]]:
    expectations = _planned_test_expectations(plan_review)
    concerns: list[dict[str, Any]] = []
    for expectation in expectations:
        source = _normal_path(expectation.get("source", ""))
        test_path = _normal_path(expectation.get("test_path", ""))
        if not test_path:
            continue
        observed = any(_path_matches(changed_path, test_path) for changed_path in changed_files)
        if observed:
            continue
        concerns.append(
            _missing_planned_test_concern(
                source=source,
                test_path=test_path,
                changed_files=changed_files,
                plan_fingerprint=plan_fingerprint,
                plan_path=plan_path,
            )
        )
    return concerns


def _public_api_migration_concerns(
    *,
    expectations: list[dict[str, Any]],
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
) -> list[dict[str, Any]]:
    concerns: list[dict[str, Any]] = []
    for expectation in expectations:
        expected_path = _normal_path(expectation.get("path", ""))
        if not expected_path:
            continue
        observed = any(_path_matches(changed_path, expected_path) for changed_path in changed_files)
        if observed:
            continue
        concerns.append(
            _missing_public_api_migration_concern(
                expectation=expectation,
                changed_files=changed_files,
                plan_fingerprint=plan_fingerprint,
                plan_path=plan_path,
            )
        )
    return concerns


def _semantic_intent_scan(
    *,
    expectations: list[dict[str, Any]],
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
    project_root: Path | None,
) -> dict[str, Any]:
    if not expectations or project_root is None:
        return {
            "concerns": [],
            "observed_semantic_intent_total": 0,
            "missing_semantic_intent_total": 0,
            "conflicting_semantic_intent_total": 0,
        }
    text_by_file = _text_by_changed_file(project_root, changed_files)
    readable_changed_files = list(text_by_file)
    concerns: list[dict[str, Any]] = []
    observed_total = 0
    missing_total = 0
    conflicting_total = 0
    for expectation in expectations:
        source = _normal_path(expectation.get("source", ""))
        scoped_files = _scoped_changed_files(readable_changed_files, source)
        if not scoped_files:
            continue
        content = "\n".join(text_by_file[path] for path in scoped_files)
        all_terms = _string_list(expectation.get("all_terms"))
        any_terms = _string_list(expectation.get("any_terms"))
        forbidden_terms = _string_list(expectation.get("forbidden_terms"))
        missing_all_terms = [term for term in all_terms if term.lower() not in content]
        missing_any_terms = any_terms if any_terms and not any(term.lower() in content for term in any_terms) else []
        observed_forbidden_terms = [term for term in forbidden_terms if term.lower() in content]
        if missing_all_terms or missing_any_terms:
            missing_total += 1
            concerns.append(
                _semantic_intent_concern(
                    observation="planned_intent_terms_not_observed",
                    expectation=expectation,
                    scoped_changed_files=scoped_files,
                    changed_files=changed_files,
                    missing_all_terms=missing_all_terms,
                    missing_any_terms=missing_any_terms,
                    observed_forbidden_terms=[],
                    plan_fingerprint=plan_fingerprint,
                    plan_path=plan_path,
                )
            )
        if observed_forbidden_terms:
            conflicting_total += 1
            concerns.append(
                _semantic_intent_concern(
                    observation="planned_intent_conflict_observed",
                    expectation=expectation,
                    scoped_changed_files=scoped_files,
                    changed_files=changed_files,
                    missing_all_terms=[],
                    missing_any_terms=[],
                    observed_forbidden_terms=observed_forbidden_terms,
                    plan_fingerprint=plan_fingerprint,
                    plan_path=plan_path,
                )
            )
        if not missing_all_terms and not missing_any_terms and not observed_forbidden_terms:
            observed_total += 1
    return {
        "concerns": concerns,
        "observed_semantic_intent_total": observed_total,
        "missing_semantic_intent_total": missing_total,
        "conflicting_semantic_intent_total": conflicting_total,
    }


def _matches_expected_test(path: str, test_expectations: list[dict[str, Any]]) -> bool:
    return any(
        _path_matches(path, _normal_path(expectation.get("test_path", "")))
        for expectation in test_expectations
    )


def _matches_public_api_migration(path: str, expectations: list[dict[str, Any]]) -> bool:
    return any(
        _path_matches(path, _normal_path(expectation.get("path", "")))
        for expectation in expectations
    )


def plan_diff_consistency_scan(
    plan_review: dict[str, Any],
    *,
    changed_files: list[str],
    project_root: str | Path | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    changed = [_normal_path(path) for path in changed_files]
    changed = [path for path in changed if path]
    planned = _planned_paths(plan_review)
    plan_fingerprint = str(plan_review.get("plan_fingerprint", "") or "")
    artifacts = plan_review.get("artifacts")
    plan_path = ""
    if isinstance(artifacts, dict):
        plan_path = _normal_path(artifacts.get("plan_path", ""))
    import_expectations = _planned_import_expectations(plan_review)
    test_expectations = _planned_test_expectations(plan_review)
    public_api_migrations = _planned_public_api_migrations(plan_review)
    semantic_intents = _planned_semantic_intents(plan_review)
    root = Path(project_root).resolve() if project_root is not None else None
    if not planned and not import_expectations and not test_expectations and not public_api_migrations and not semantic_intents:
        return {
            "concerns": [],
            "changed_file_total": len(changed),
            "planned_path_total": len(planned),
            "planned_import_total": 0,
            "planned_import_alternative_total": 0,
            "observed_planned_import_total": 0,
            "missing_planned_import_total": 0,
            "expected_test_total": 0,
            "observed_expected_test_total": 0,
            "missing_expected_test_total": 0,
            "public_api_migration_total": 0,
            "observed_public_api_migration_total": 0,
            "missing_public_api_migration_total": 0,
            "semantic_intent_total": 0,
            "observed_semantic_intent_total": 0,
            "missing_semantic_intent_total": 0,
            "conflicting_semantic_intent_total": 0,
            "scoped_to_changed_files": True,
        }

    concerns: list[dict[str, Any]] = []
    for path in changed:
        if not any(_path_matches(path, planned_path) for planned_path in planned) and not _matches_expected_test(
            path,
            test_expectations,
        ) and not _matches_public_api_migration(
            path,
            public_api_migrations,
        ):
            concerns.append(
                _unexpected_change_concern(
                    path=path,
                    planned_paths=planned,
                    plan_fingerprint=plan_fingerprint,
                    plan_path=plan_path,
                )
            )
    for path in planned:
        if not any(_path_matches(changed_path, path) for changed_path in changed):
            concerns.append(
                _missing_planned_path_concern(
                    path=path,
                    changed_files=changed,
                    plan_fingerprint=plan_fingerprint,
                    plan_path=plan_path,
                )
            )
    import_scan = _import_expectation_scan(
        expectations=import_expectations,
        changed_files=changed,
        plan_fingerprint=plan_fingerprint,
        plan_path=plan_path,
        project_root=root,
    )
    import_concerns = import_scan.get("concerns")
    if isinstance(import_concerns, list):
        concerns.extend(import_concerns)
    test_concerns = _test_expectation_concerns(
        plan_review=plan_review,
        changed_files=changed,
        plan_fingerprint=plan_fingerprint,
        plan_path=plan_path,
    )
    concerns.extend(test_concerns)
    public_api_migration_concerns = _public_api_migration_concerns(
        expectations=public_api_migrations,
        changed_files=changed,
        plan_fingerprint=plan_fingerprint,
        plan_path=plan_path,
    )
    concerns.extend(public_api_migration_concerns)
    semantic_scan = _semantic_intent_scan(
        expectations=semantic_intents,
        changed_files=changed,
        plan_fingerprint=plan_fingerprint,
        plan_path=plan_path,
        project_root=root,
    )
    semantic_concerns = semantic_scan.get("concerns")
    if isinstance(semantic_concerns, list):
        concerns.extend(semantic_concerns)
    concerns.sort(
        key=lambda item: (
            str(item.get("level", "") or ""),
            str(item.get("location", {}).get("path", "") if isinstance(item.get("location"), dict) else ""),
            str(item.get("concern_id", "") or ""),
        )
    )
    return {
        "concerns": concerns[:limit],
        "changed_file_total": len(changed),
        "planned_path_total": len(planned),
        "planned_import_total": len(import_expectations),
        "planned_import_alternative_total": sum(1 for item in import_expectations if item.get("alternative")),
        "observed_planned_import_total": int(import_scan.get("observed_import_total", 0) or 0),
        "missing_planned_import_total": int(import_scan.get("missing_import_total", 0) or 0),
        "expected_test_total": len(test_expectations),
        "observed_expected_test_total": len(test_expectations) - len(test_concerns),
        "missing_expected_test_total": len(test_concerns),
        "public_api_migration_total": len(public_api_migrations),
        "observed_public_api_migration_total": len(public_api_migrations) - len(public_api_migration_concerns),
        "missing_public_api_migration_total": len(public_api_migration_concerns),
        "semantic_intent_total": len(semantic_intents),
        "observed_semantic_intent_total": int(semantic_scan.get("observed_semantic_intent_total", 0) or 0),
        "missing_semantic_intent_total": int(semantic_scan.get("missing_semantic_intent_total", 0) or 0),
        "conflicting_semantic_intent_total": int(semantic_scan.get("conflicting_semantic_intent_total", 0) or 0),
        "concern_total_before_limit": len(concerns),
        "scoped_to_changed_files": True,
    }


__all__ = [
    "load_plan_review",
    "plan_diff_consistency_scan",
]
