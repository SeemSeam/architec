from __future__ import annotations

import ast
import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {
    ".architec",
    ".git",
    ".hippocampus",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
}


@dataclass(frozen=True)
class _FunctionFingerprint:
    path: str
    line: int
    symbol: str
    fingerprint: str
    node_count: int


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
        if any(part in SKIP_DIRS for part in path.parts):
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


def _candidate_key(item: _FunctionFingerprint) -> tuple[str, int, str]:
    return (item.path, item.line, item.symbol)


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
