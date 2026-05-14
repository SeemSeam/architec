from __future__ import annotations

import ast
import copy
import hashlib
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
