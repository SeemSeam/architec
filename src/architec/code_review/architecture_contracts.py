from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from architec.support.architecture_rules import (
    ArchitectureContractRule,
    load_archi_rules,
    path_is_ignored,
)
from architec.support.io_utils import normalize_relpath


@dataclass(frozen=True)
class _ImportRecord:
    module: str
    line: int


def _normal_path(path: object) -> str:
    text = normalize_relpath(str(path or ""))
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def _path_matches(path: str, pattern: str) -> bool:
    normalized = _normal_path(path)
    normalized_pattern = _normal_path(pattern)
    if not normalized or not normalized_pattern:
        return False
    rel_posix = PurePosixPath(normalized)
    return (
        fnmatchcase(normalized, normalized_pattern)
        or rel_posix.match(normalized_pattern)
        or normalized == normalized_pattern
        or normalized.startswith(f"{normalized_pattern.rstrip('/')}/")
    )


def _module_matches(module: str, pattern: str) -> bool:
    target = str(module or "").strip()
    candidate = str(pattern or "").strip()
    if not target or not candidate:
        return False
    if "*" in candidate or "?" in candidate or "[" in candidate:
        return fnmatchcase(target, candidate)
    return target == candidate or target.startswith(f"{candidate}.")


def _module_for_path(path: str) -> tuple[str, bool]:
    normalized = _normal_path(path)
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    parts = [part for part in normalized.split("/") if part]
    if parts and parts[0] == "src" and len(parts) >= 2:
        parts = parts[1:]
    is_init = bool(parts and parts[-1] == "__init__")
    if is_init:
        parts = parts[:-1]
    return ".".join(parts), is_init


def _resolve_relative_module(path: str, *, level: int, module: str) -> str:
    current_module, is_init = _module_for_path(path)
    parts = [part for part in current_module.split(".") if part]
    if not is_init and parts:
        parts = parts[:-1]
    if level > 1:
        parts = parts[: max(0, len(parts) - (level - 1))]
    if module:
        parts.extend(part for part in module.split(".") if part)
    return ".".join(parts)


def _import_records(path: str, source: str) -> list[_ImportRecord]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    records: list[_ImportRecord] = []
    seen: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = str(alias.name or "").strip()
                key = (module, int(getattr(node, "lineno", 0) or 0))
                if module and key not in seen:
                    seen.add(key)
                    records.append(_ImportRecord(module=module, line=key[1]))
            continue
        if isinstance(node, ast.ImportFrom):
            raw_module = str(node.module or "").strip()
            module = (
                _resolve_relative_module(path, level=int(node.level or 0), module=raw_module)
                if int(node.level or 0) > 0
                else raw_module
            )
            line = int(getattr(node, "lineno", 0) or 0)
            modules = [module] if module else []
            for alias in node.names:
                alias_name = str(alias.name or "").strip()
                if module and alias_name and alias_name != "*":
                    modules.append(f"{module}.{alias_name}")
            for item in modules:
                key = (item, line)
                if key not in seen:
                    seen.add(key)
                    records.append(_ImportRecord(module=item, line=line))
    return records


def _stable_concern_id(
    *,
    path: str,
    line: int,
    rule: ArchitectureContractRule,
    module: str,
    pattern: str,
) -> str:
    payload = {
        "kind": "architecture-contract",
        "path": path,
        "line": line,
        "rule_id": rule.rule_id,
        "module": module,
        "pattern": pattern,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:architecture-contract:{digest}"


def _concern(
    *,
    path: str,
    record: _ImportRecord,
    rule: ArchitectureContractRule,
    pattern: str,
) -> dict[str, Any]:
    evidence = [
        f"architecture_contract.rule_id={rule.rule_id}",
        f"architecture_contract.source_glob={rule.source_glob}",
        f"architecture_contract.import={record.module}",
        f"architecture_contract.restricted_import={pattern}",
    ]
    if rule.owner:
        evidence.append(f"architecture_contract.owner={rule.owner}")
    next_steps_hint = "Review whether this dependency should route through the intended boundary."
    if rule.note:
        next_steps_hint = rule.note
    location = {
        "path": path,
        "line": record.line,
        "symbol": "",
        "symbol_kind": "module",
    }
    return {
        "concern_id": _stable_concern_id(
            path=path,
            line=record.line,
            rule=rule,
            module=record.module,
            pattern=pattern,
        ),
        "kind": "architecture-contract",
        "level": "caution",
        "confidence": 0.9,
        "location": location,
        "root_cause": "Changed file imports a module matched by an architecture contract.",
        "evidence": evidence,
        "blast_radius": [path],
        "next_steps_hint": next_steps_hint,
    }


def _matches_rule(path: str, rule: ArchitectureContractRule) -> bool:
    return _path_matches(path, rule.source_glob)


def _concerns_for_file(
    project_root: Path,
    path: str,
    rules: tuple[ArchitectureContractRule, ...],
) -> list[dict[str, Any]]:
    target = project_root / path
    if target.suffix != ".py" or not target.exists():
        return []
    matching_rules = [rule for rule in rules if _matches_rule(path, rule)]
    if not matching_rules:
        return []
    try:
        source = target.read_text(encoding="utf-8")
    except OSError:
        return []
    records = _import_records(path, source)
    concerns: list[dict[str, Any]] = []
    seen_matches: set[tuple[str, str, int]] = set()
    for rule in matching_rules:
        for record in records:
            for pattern in rule.restricted_imports:
                if _module_matches(record.module, pattern):
                    key = (rule.rule_id, pattern, record.line)
                    if key in seen_matches:
                        continue
                    seen_matches.add(key)
                    concerns.append(
                        _concern(
                            path=path,
                            record=record,
                            rule=rule,
                            pattern=pattern,
                        )
                    )
    return concerns


def architecture_contract_scan(
    project_root: str | Path,
    *,
    changed_files: Iterable[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    rules = load_archi_rules(root)
    contract_rules = tuple(rules.architecture_contract_rules)
    changed = [_normal_path(path) for path in (changed_files or [])]
    changed = [path for path in changed if path]
    if not contract_rules or not changed:
        return {
            "concerns": [],
            "rule_total": len(contract_rules),
            "checked_file_total": 0,
            "scoped_to_changed_files": bool(changed),
        }
    concerns: list[dict[str, Any]] = []
    checked_file_total = 0
    seen_files: set[str] = set()
    for path in changed:
        if path in seen_files or path_is_ignored(path, rules):
            continue
        seen_files.add(path)
        target = root / path
        if target.suffix != ".py" or not target.exists():
            continue
        checked_file_total += 1
        concerns.extend(_concerns_for_file(root, path, contract_rules))
    concerns.sort(
        key=lambda item: (
            str(item.get("location", {}).get("path", "") if isinstance(item.get("location"), dict) else ""),
            int(item.get("location", {}).get("line", 0) if isinstance(item.get("location"), dict) else 0),
            str(item.get("concern_id", "") or ""),
        )
    )
    return {
        "concerns": concerns[:limit],
        "rule_total": len(contract_rules),
        "checked_file_total": checked_file_total,
        "concern_total_before_limit": len(concerns),
        "scoped_to_changed_files": True,
    }


__all__ = ["architecture_contract_scan"]
