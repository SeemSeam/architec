from __future__ import annotations

import ast
import copy
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {
    ".architec",
    ".cache",
    ".ccb",
    ".git",
    ".hippocampus",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "env",
    "fixtures",
    "generated",
    "htmlcov",
    "local-test-env",
    "node_modules",
    "out",
    "release-flow-test",
    "site-packages",
    "target",
    "temp",
    "test",
    "tests",
    "third-party",
    "third_party",
    "tmp",
    "venv",
    "vendor",
}


@dataclass(frozen=True)
class _FunctionFingerprint:
    path: str
    line: int
    symbol: str
    fingerprint: str
    node_count: int
    thin_wrapper_call: str = ""


class _NormalizeAst(ast.NodeTransformer):
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802
        node.name = "_fn"
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:  # noqa: N802
        node.name = "_fn"
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:  # noqa: N802
        node.arg = "_arg"
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:  # noqa: N802
        node.id = "_name"
        self.generic_visit(node)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:  # noqa: N802
        node.attr = "_attr"
        self.generic_visit(node)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:  # noqa: N802
        if isinstance(node.value, str):
            node.value = "_str"
        elif isinstance(node.value, (int, float, complex)):
            node.value = 0
        elif isinstance(node.value, bytes):
            node.value = b"_bytes"
        self.generic_visit(node)
        return node


def _iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            parts = path.parts
        if any(part in SKIP_DIRS for part in parts[:-1]):
            continue
        files.append(path)
    return sorted(files)


def _symbol_for(node: ast.AST, parents: list[str]) -> str:
    name = str(getattr(node, "name", "") or "<anonymous>")
    if parents:
        return ".".join([*parents, name])
    return name


def _node_size(node: ast.AST) -> int:
    return sum(1 for _ in ast.walk(node))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        if base:
            return f"{base}.{node.attr}"
        return node.attr
    return ""


def _called_target(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return ""


def _thin_wrapper_call_target(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    body = list(node.body)
    control_nodes = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match)
    nested_defs = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    if not body or any(isinstance(item, control_nodes) for item in ast.walk(node)):
        return ""
    if any(isinstance(item, nested_defs) and item is not node for item in ast.walk(node)):
        return ""
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
        body = body[1:]
    if not body or len(body) > 4:
        return ""
    simple_statements = (ast.Assign, ast.AnnAssign, ast.Expr, ast.Return)
    if any(not isinstance(item, simple_statements) for item in body):
        return ""

    terminal = body[-1]
    if isinstance(terminal, ast.Return):
        target = _called_target(terminal.value)
    elif isinstance(terminal, ast.Expr):
        target = _called_target(terminal.value)
    else:
        target = ""
    if not target or target in {"super"}:
        return ""
    return target


def _fingerprint(node: ast.AST) -> str:
    normalized = _NormalizeAst().visit(ast.fix_missing_locations(copy.deepcopy(node)))
    text = ast.dump(normalized, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _stable_concern_id(
    duplicate: _FunctionFingerprint,
    reference: _FunctionFingerprint,
    fingerprint: str,
) -> str:
    payload = "|".join(
        [
            "duplication",
            duplicate.path,
            str(duplicate.line),
            duplicate.symbol,
            reference.path,
            str(reference.line),
            reference.symbol,
            fingerprint,
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"code-review:duplication:{digest}"


def _stable_family_concern_id(
    members: list[_FunctionFingerprint],
    fingerprint: str,
    family_key: str,
) -> str:
    payload = {
        "kind": "duplication",
        "scope": "variant-family",
        "path": members[0].path,
        "family_key": family_key,
        "fingerprint": fingerprint,
        "members": [item.symbol for item in members],
    }
    encoded = repr(payload)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:duplication:{digest}"


def _candidate_key(item: _FunctionFingerprint) -> tuple[str, int, str]:
    return (item.path, item.line, item.symbol)


def _symbol_tokens(symbol: str) -> list[str]:
    leaf = symbol.rsplit(".", 1)[-1]
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", leaf)
    spaced = re.sub(r"[^A-Za-z0-9]+", " ", spaced)
    return [token.lower() for token in spaced.split() if token]


def _variant_family_key(symbol: str) -> str:
    tokens = _symbol_tokens(symbol)
    if len(tokens) < 2:
        return ""
    normalized: list[str] = []
    variant_seen = False
    previous_variant_label = False
    for token in tokens:
        if token in {"phase", "step", "stage", "part"}:
            normalized.append(token)
            previous_variant_label = True
            continue
        if previous_variant_label and re.fullmatch(r"\d+[a-z]?", token):
            variant_seen = True
            previous_variant_label = False
            continue
        previous_variant_label = False
        labeled = re.fullmatch(r"(phase|step|stage|part|v)\d+[a-z]?", token)
        if labeled:
            normalized.append(labeled.group(1))
            variant_seen = True
            continue
        suffixed = re.fullmatch(r"([a-z][a-z_]*?)(\d+[a-z]?)", token)
        if suffixed and len(suffixed.group(1)) >= 3:
            normalized.append(suffixed.group(1))
            variant_seen = True
            continue
        if re.fullmatch(r"\d+[a-z]?", token):
            variant_seen = True
            continue
        normalized.append(token)
    return " ".join(normalized) if variant_seen and len(normalized) >= 2 else ""


def _collect_functions(path: Path, root: Path) -> list[_FunctionFingerprint]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    relpath = path.relative_to(root).as_posix()
    found: list[_FunctionFingerprint] = []

    def visit(node: ast.AST, parents: list[str]) -> None:
        next_parents = parents
        if isinstance(node, ast.ClassDef):
            next_parents = [*parents, node.name]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            size = _node_size(node)
            if size >= 25:
                found.append(
                    _FunctionFingerprint(
                        path=relpath,
                        line=int(getattr(node, "lineno", 0) or 0),
                        symbol=_symbol_for(node, parents),
                        fingerprint=_fingerprint(node),
                        node_count=size,
                        thin_wrapper_call=_thin_wrapper_call_target(node),
                    )
                )
            next_parents = [*parents, str(getattr(node, "name", "") or "")]
        for child in ast.iter_child_nodes(node):
            visit(child, next_parents)

    visit(tree, [])
    return found


def _build_concern(
    duplicate: _FunctionFingerprint,
    reference: _FunctionFingerprint,
    fingerprint: str,
) -> dict[str, Any]:
    return {
        "concern_id": _stable_concern_id(duplicate, reference, fingerprint),
        "kind": "duplication",
        "level": "caution",
        "confidence": 0.9,
        "location": {
            "path": duplicate.path,
            "line": duplicate.line,
            "symbol": duplicate.symbol,
            "symbol_kind": "function",
        },
        "root_cause": "Function has the same normalized AST fingerprint as another function.",
        "evidence": [
            f"near_duplicate.fingerprint={fingerprint}",
            f"near_duplicate.reference={reference.path}:{reference.line}:{reference.symbol}",
            f"near_duplicate.node_count={duplicate.node_count}",
        ],
        "references": [
            {
                "role": "reference",
                "path": reference.path,
                "line": reference.line,
                "symbol": reference.symbol,
                "symbol_kind": "function",
            }
        ],
        "blast_radius": [duplicate.path, reference.path],
        "next_steps_hint": "Review whether one implementation can reuse or call the other.",
    }


def _build_variant_family_concern(
    members: list[_FunctionFingerprint],
    fingerprint: str,
    family_key: str,
) -> dict[str, Any] | None:
    pair = _variant_family_representative_pair(members)
    if pair is None:
        return None
    reference, duplicate = pair
    return {
        "concern_id": _stable_family_concern_id(members, fingerprint, family_key),
        "kind": "duplication",
        "level": "caution",
        "confidence": 0.82,
        "location": {
            "path": duplicate.path,
            "line": duplicate.line,
            "symbol": duplicate.symbol,
            "symbol_kind": "function",
        },
        "root_cause": "Same-file function family shares one normalized AST fingerprint across variant members.",
        "evidence": [
            f"near_duplicate.fingerprint={fingerprint}",
            f"near_duplicate.variant_family={family_key}",
            f"near_duplicate.variant_member_total={len(members)}",
            f"near_duplicate.reference={reference.path}:{reference.line}:{reference.symbol}",
            f"near_duplicate.node_count={duplicate.node_count}",
        ],
        "references": [
            {
                "role": "reference",
                "path": reference.path,
                "line": reference.line,
                "symbol": reference.symbol,
                "symbol_kind": "function",
            }
        ],
        "blast_radius": [reference.path],
        "next_steps_hint": "Review whether the variant family should stay explicit or share a common helper.",
    }


def _normalized_changed_files(changed_files: Iterable[str] | None) -> frozenset[str] | None:
    if changed_files is None:
        return None
    normalized = {
        Path(str(path)).as_posix().lstrip("./")
        for path in changed_files
        if str(path or "").strip()
    }
    return frozenset(normalized)


def _reference_for_scoped_candidate(
    candidate: _FunctionFingerprint,
    group: list[_FunctionFingerprint],
) -> _FunctionFingerprint:
    for item in group:
        if item != candidate:
            return item
    return group[0]


def _is_thin_wrapper_pair(
    duplicate: _FunctionFingerprint,
    reference: _FunctionFingerprint,
) -> bool:
    return bool(
        duplicate.thin_wrapper_call
        and reference.thin_wrapper_call
        and duplicate.thin_wrapper_call != reference.thin_wrapper_call
    )


def _variant_family_representative_pair(
    members: list[_FunctionFingerprint],
) -> tuple[_FunctionFingerprint, _FunctionFingerprint] | None:
    for reference in members:
        for duplicate in members:
            if duplicate == reference:
                continue
            if not _is_thin_wrapper_pair(duplicate, reference):
                return reference, duplicate
    return None


def _variant_family_groups(
    group: list[_FunctionFingerprint],
) -> dict[tuple[str, str], list[_FunctionFingerprint]]:
    families: dict[tuple[str, str], list[_FunctionFingerprint]] = {}
    for item in group:
        family_key = _variant_family_key(item.symbol)
        if not family_key:
            continue
        families.setdefault((item.path, family_key), []).append(item)
    return {
        key: sorted(items, key=_candidate_key)
        for key, items in families.items()
        if len(items) >= 2
    }


def _same_variant_family(
    left: _FunctionFingerprint,
    right: _FunctionFingerprint,
    grouped_keys: set[tuple[str, str]],
) -> bool:
    if left.path != right.path:
        return False
    left_key = _variant_family_key(left.symbol)
    right_key = _variant_family_key(right.symbol)
    return bool(left_key and left_key == right_key and (left.path, left_key) in grouped_keys)


def _candidate_keys(items: Iterable[_FunctionFingerprint]) -> set[tuple[str, int, str]]:
    return {_candidate_key(item) for item in items}


def near_duplicate_scan(
    project_root: str | Path,
    *,
    limit: int = 20,
    changed_files: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    changed_scope = _normalized_changed_files(changed_files)
    by_fingerprint: dict[str, list[_FunctionFingerprint]] = {}
    for path in _iter_python_files(root):
        for item in _collect_functions(path, root):
            by_fingerprint.setdefault(item.fingerprint, []).append(item)

    concerns: list[dict[str, Any]] = []
    candidate_total_before_scope = 0
    for fingerprint, items in sorted(by_fingerprint.items()):
        if len(items) < 2:
            continue
        group = sorted(items, key=_candidate_key)
        candidate_total_before_scope += len(group) - 1
        families = _variant_family_groups(group)
        grouped_keys = set(families)
        grouped_member_keys: set[tuple[str, int, str]] = set()
        for (path, family_key), members in sorted(families.items()):
            if changed_scope is not None and path not in changed_scope:
                continue
            concern = _build_variant_family_concern(members, fingerprint, family_key)
            if not concern:
                continue
            concerns.append(concern)
            grouped_member_keys.update(_candidate_keys(members))
        if changed_scope is None:
            reference = group[0]
            candidates = group[1:]
        else:
            candidates = [item for item in group if item.path in changed_scope]
        for duplicate in candidates:
            reference = (
                _reference_for_scoped_candidate(duplicate, group)
                if changed_scope is not None
                else reference
            )
            if _same_variant_family(duplicate, reference, grouped_keys):
                continue
            if _candidate_key(duplicate) in grouped_member_keys:
                continue
            if _is_thin_wrapper_pair(duplicate, reference):
                continue
            concerns.append(_build_concern(duplicate, reference, fingerprint))
    result: dict[str, Any] = {
        "concerns": concerns[:limit],
        "candidate_total_before_scope": candidate_total_before_scope,
    }
    if changed_scope is not None:
        result["scoped_to_changed_files"] = True
        result["changed_file_total"] = len(changed_scope)
    return result


def near_duplicate_concerns(project_root: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    return list(near_duplicate_scan(project_root, limit=limit)["concerns"])


__all__ = ["near_duplicate_concerns", "near_duplicate_scan"]
