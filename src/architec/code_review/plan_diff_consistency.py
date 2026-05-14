from __future__ import annotations

import hashlib
import json
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any

from architec.code_review.python_imports import import_records, module_matches
from architec.support.io_utils import normalize_relpath


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


def _planned_import_expectations(plan_review: dict[str, Any]) -> list[dict[str, Any]]:
    understood = plan_review.get("understood_plan")
    if not isinstance(understood, dict):
        return []
    raw_dependencies = understood.get("dependencies")
    if not isinstance(raw_dependencies, list):
        return []
    expectations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
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


def _scoped_changed_files(changed_files: list[str], source: str) -> list[str]:
    if not source:
        return changed_files
    return [path for path in changed_files if _path_matches(path, source)]


def _import_expectation_concerns(
    *,
    plan_review: dict[str, Any],
    changed_files: list[str],
    plan_fingerprint: str,
    plan_path: str,
    project_root: Path | None,
) -> list[dict[str, Any]]:
    expectations = _planned_import_expectations(plan_review)
    if not expectations or project_root is None:
        return []
    imports_by_file = _imports_by_changed_file(project_root, changed_files)
    changed_python_files = list(imports_by_file)
    concerns: list[dict[str, Any]] = []
    for expectation in expectations:
        source = _normal_path(expectation.get("source", ""))
        module = str(expectation.get("module", "") or "").strip()
        if not module:
            continue
        scoped_files = _scoped_changed_files(changed_python_files, source)
        if not scoped_files:
            continue
        observed = any(
            module_matches(imported, module)
            for path in scoped_files
            for imported in imports_by_file.get(path, [])
        )
        if observed:
            continue
        concerns.append(
            _missing_planned_import_concern(
                source=source,
                module=module,
                changed_files=changed_files,
                scoped_changed_files=scoped_files,
                plan_fingerprint=plan_fingerprint,
                plan_path=plan_path,
            )
        )
    return concerns


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


def _matches_expected_test(path: str, test_expectations: list[dict[str, Any]]) -> bool:
    return any(
        _path_matches(path, _normal_path(expectation.get("test_path", "")))
        for expectation in test_expectations
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
    root = Path(project_root).resolve() if project_root is not None else None
    if not planned and not import_expectations and not test_expectations:
        return {
            "concerns": [],
            "changed_file_total": len(changed),
            "planned_path_total": len(planned),
            "planned_import_total": 0,
            "expected_test_total": 0,
            "observed_expected_test_total": 0,
            "missing_expected_test_total": 0,
            "scoped_to_changed_files": True,
        }

    concerns: list[dict[str, Any]] = []
    for path in changed:
        if not any(_path_matches(path, planned_path) for planned_path in planned) and not _matches_expected_test(
            path,
            test_expectations,
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
    concerns.extend(
        _import_expectation_concerns(
            plan_review=plan_review,
            changed_files=changed,
            plan_fingerprint=plan_fingerprint,
            plan_path=plan_path,
            project_root=root,
        )
    )
    test_concerns = _test_expectation_concerns(
        plan_review=plan_review,
        changed_files=changed,
        plan_fingerprint=plan_fingerprint,
        plan_path=plan_path,
    )
    concerns.extend(test_concerns)
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
        "expected_test_total": len(test_expectations),
        "observed_expected_test_total": len(test_expectations) - len(test_concerns),
        "missing_expected_test_total": len(test_concerns),
        "concern_total_before_limit": len(concerns),
        "scoped_to_changed_files": True,
    }


__all__ = [
    "load_plan_review",
    "plan_diff_consistency_scan",
]
