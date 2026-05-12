from __future__ import annotations

import ast
import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def near_duplicate_concerns(project_root: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    root = Path(project_root)
    by_fingerprint: dict[str, list[_FunctionFingerprint]] = {}
    for path in _iter_python_files(root):
        for item in _collect_functions(path, root):
            by_fingerprint.setdefault(item.fingerprint, []).append(item)

    concerns: list[dict[str, Any]] = []
    for fingerprint, items in sorted(by_fingerprint.items()):
        if len(items) < 2:
            continue
        reference = sorted(items, key=lambda item: (item.path, item.line, item.symbol))[0]
        for duplicate in sorted(items, key=lambda item: (item.path, item.line, item.symbol))[1:]:
            concerns.append(
                {
                    "concern_id": f"code-review:near-duplicate:{len(concerns) + 1}",
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
                    "blast_radius": [duplicate.path, reference.path],
                    "next_steps_hint": "Review whether one implementation can reuse or call the other.",
                }
            )
            if len(concerns) >= limit:
                return concerns
    return concerns


__all__ = ["near_duplicate_concerns"]
