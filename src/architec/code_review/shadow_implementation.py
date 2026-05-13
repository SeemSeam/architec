from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any


SKIP_DIRS = {
    ".architec",
    ".git",
    ".hippocampus",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "fixtures",
    "generated",
    "htmlcov",
    "node_modules",
    "test",
    "tests",
    "venv",
    "vendor",
}

ROLE_ALIASES = {
    "map": "mapper",
    "mapping": "mapper",
    "parse": "parser",
    "reporting": "report",
    "score": "scoring",
    "select": "selection",
    "selector": "selection",
}
ROLE_TOKENS = {
    "cleanup",
    "component",
    "filter",
    "mapper",
    "parser",
    "policy",
    "report",
    "review",
    "scoring",
    "selection",
    "status",
}
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "by",
    "for",
    "from",
    "get",
    "has",
    "in",
    "is",
    "make",
    "new",
    "of",
    "old",
    "or",
    "run",
    "set",
    "the",
    "to",
    "with",
}
ADAPTER_TOKENS = {
    "adapter",
    "bridge",
    "compat",
    "delegate",
    "delegating",
    "delegation",
    "facade",
    "proxy",
    "shim",
    "wrapper",
}

MIN_NODE_COUNT = 45
MIN_NAME_OVERLAP = 0.45
MIN_SIGNATURE_SIMILARITY = 0.6
MIN_AST_SIMILARITY = 0.82
MIN_CONFIDENCE = 0.78


@dataclass(frozen=True)
class _FunctionCandidate:
    path: str
    line: int
    symbol: str
    symbol_kind: str
    node_count: int
    fingerprint: str
    name_tokens: frozenset[str]
    all_tokens: frozenset[str]
    role_tokens: frozenset[str]
    signature_tokens: frozenset[str]
    parameter_count: int
    feature_vector: dict[str, float]
    names: frozenset[str]
    calls: frozenset[str]
    attrs: frozenset[str]
    imports: frozenset[str]

    @property
    def module_tokens(self) -> frozenset[str]:
        return frozenset(_tokens(Path(self.path).stem))


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


def _tokens(text: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    spaced = re.sub(r"[^A-Za-z0-9]+", " ", spaced)
    return [token.lower() for token in spaced.split() if token]


def _meaningful_tokens(text: str) -> frozenset[str]:
    return frozenset(token for token in _tokens(text) if token not in STOPWORDS)


def _role_tokens(tokens: set[str]) -> frozenset[str]:
    roles = {ROLE_ALIASES.get(token, token) for token in tokens}
    return frozenset(token for token in roles if token in ROLE_TOKENS)


def _is_adapter_like(tokens: set[str]) -> bool:
    return bool(tokens & ADAPTER_TOKENS)


def _iter_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def _node_count(node: ast.AST) -> int:
    return sum(1 for _ in ast.walk(node))


def _fingerprint(node: ast.AST) -> str:
    normalized = _NormalizeAst().visit(ast.fix_missing_locations(copy.deepcopy(node)))
    text = ast.dump(normalized, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _feature_vector(node: ast.AST) -> dict[str, float]:
    counts: Counter[str] = Counter()
    for child in ast.walk(node):
        if isinstance(child, (ast.Load, ast.Store, ast.Del)):
            continue
        name = type(child).__name__
        counts[f"node:{name}"] += 1
        if isinstance(child, ast.operator):
            counts[f"op:{name}"] += 1
        elif isinstance(child, ast.cmpop):
            counts[f"cmp:{name}"] += 1
        elif isinstance(child, ast.boolop):
            counts[f"bool:{name}"] += 1
        elif isinstance(child, ast.unaryop):
            counts[f"unary:{name}"] += 1
        elif isinstance(child, ast.Constant):
            counts[f"constant:{type(child.value).__name__}"] += 1
    return {key: float(value) for key, value in counts.items()}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    keys = set(left) | set(right)
    numerator = sum(left.get(key, 0.0) * right.get(key, 0.0) for key in keys)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _jaccard(left: set[str] | frozenset[str], right: set[str] | frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _signature_tokens(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[frozenset[str], int]:
    args = [
        *node.args.posonlyargs,
        *node.args.args,
        *node.args.kwonlyargs,
    ]
    names = [arg.arg for arg in args if arg.arg not in {"self", "cls"}]
    tokens = {token for name in names for token in _tokens(name) if token not in STOPWORDS}
    if node.args.vararg is not None:
        tokens.add("vararg")
        names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        tokens.add("kwarg")
        names.append(node.args.kwarg.arg)
    return frozenset(tokens), len(names)


def _signature_similarity(left: _FunctionCandidate, right: _FunctionCandidate) -> float:
    largest = max(left.parameter_count, right.parameter_count, 1)
    arity = 1.0 - (abs(left.parameter_count - right.parameter_count) / largest)
    token_overlap = _jaccard(left.signature_tokens, right.signature_tokens)
    return (0.6 * arity) + (0.4 * token_overlap)


def _module_imports(tree: ast.AST) -> frozenset[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.rsplit(".", 1)[-1].lower())
                if alias.asname:
                    imports.add(alias.asname.lower())
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.rsplit(".", 1)[-1].lower())
            for alias in node.names:
                imports.add(alias.name.lower())
                if alias.asname:
                    imports.add(alias.asname.lower())
    return frozenset(imports)


def _references(node: ast.AST) -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    names: set[str] = set()
    calls: set[str] = set()
    attrs: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id.lower())
        elif isinstance(child, ast.Attribute):
            attrs.add(child.attr.lower())
        elif isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                calls.add(func.id.lower())
            elif isinstance(func, ast.Attribute):
                calls.add(func.attr.lower())
    return frozenset(names), frozenset(calls), frozenset(attrs)


def _collect_functions(path: Path, root: Path) -> list[_FunctionCandidate]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    relpath = path.relative_to(root).as_posix()
    imports = _module_imports(tree)
    found: list[_FunctionCandidate] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.class_stack: list[str] = []
            self.function_depth = 0

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
            self._collect(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
            self._collect(node)

        def _collect(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            if self.function_depth:
                return
            self.function_depth += 1
            try:
                size = _node_count(node)
                if size < MIN_NODE_COUNT:
                    return
                symbol = ".".join([*self.class_stack, node.name]) if self.class_stack else node.name
                symbol_tokens = _meaningful_tokens(symbol)
                path_tokens = _meaningful_tokens(relpath)
                all_tokens = set(symbol_tokens) | set(path_tokens)
                if _is_adapter_like(all_tokens):
                    return
                roles = _role_tokens(all_tokens)
                if not roles:
                    return
                signature_tokens, parameter_count = _signature_tokens(node)
                names, calls, attrs = _references(node)
                found.append(
                    _FunctionCandidate(
                        path=relpath,
                        line=int(getattr(node, "lineno", 0) or 0),
                        symbol=symbol,
                        symbol_kind="function",
                        node_count=size,
                        fingerprint=_fingerprint(node),
                        name_tokens=symbol_tokens,
                        all_tokens=frozenset(all_tokens),
                        role_tokens=roles,
                        signature_tokens=signature_tokens,
                        parameter_count=parameter_count,
                        feature_vector=_feature_vector(node),
                        names=names,
                        calls=calls,
                        attrs=attrs,
                        imports=imports,
                    )
                )
            finally:
                self.function_depth -= 1

    Visitor().visit(tree)
    return found


def _has_reuse_edge(source: _FunctionCandidate, target: _FunctionCandidate) -> bool:
    target_leaf = target.symbol.rsplit(".", 1)[-1].lower()
    target_tokens = {
        target.symbol.lower(),
        target_leaf,
        Path(target.path).stem.lower(),
    }
    references = set(source.calls) | set(source.attrs) | set(source.names) | set(source.imports)
    return bool(target_tokens & references)


def _primary_role(roles: set[str] | frozenset[str]) -> str:
    for role in sorted(roles):
        if role != "component":
            return role
    return "component"


def _confidence(name_overlap: float, signature_similarity: float, ast_similarity: float) -> float:
    confidence = (
        0.78
        + max(ast_similarity - MIN_AST_SIMILARITY, 0.0) * 0.45
        + max(signature_similarity - MIN_SIGNATURE_SIMILARITY, 0.0) * 0.2
        + max(name_overlap - MIN_NAME_OVERLAP, 0.0) * 0.2
    )
    return round(min(confidence, 0.97), 2)


def _stable_concern_id(
    duplicate: _FunctionCandidate,
    existing: _FunctionCandidate,
    *,
    role: str,
    name_overlap: float,
    signature_similarity: float,
    ast_similarity: float,
) -> str:
    payload = {
        "kind": "shadow-implementation",
        "duplicate": {
            "path": duplicate.path,
            "line": duplicate.line,
            "symbol": duplicate.symbol,
        },
        "existing": {
            "path": existing.path,
            "line": existing.line,
            "symbol": existing.symbol,
        },
        "role": role,
        "name_overlap": round(name_overlap, 4),
        "signature_similarity": round(signature_similarity, 4),
        "ast_similarity": round(ast_similarity, 4),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
    return f"code-review:shadow-implementation:{digest}"


def _candidate_key(item: _FunctionCandidate) -> tuple[str, int, str]:
    return (item.path, item.line, item.symbol)


def _build_concern(
    left: _FunctionCandidate,
    right: _FunctionCandidate,
    *,
    role: str,
    name_overlap: float,
    signature_similarity: float,
    ast_similarity: float,
) -> dict[str, Any]:
    existing, duplicate = sorted([left, right], key=_candidate_key)
    confidence = _confidence(name_overlap, signature_similarity, ast_similarity)
    evidence = [
        f"shadow_implementation.name_overlap={name_overlap:.2f}",
        f"shadow_implementation.signature_similarity={signature_similarity:.2f}",
        f"shadow_implementation.ast_similarity={ast_similarity:.2f}",
        f"shadow_implementation.role={role}",
        "shadow_implementation.reuse_edge=false",
        f"shadow_implementation.node_counts={duplicate.node_count}/{existing.node_count}",
    ]
    return {
        "concern_id": _stable_concern_id(
            duplicate,
            existing,
            role=role,
            name_overlap=name_overlap,
            signature_similarity=signature_similarity,
            ast_similarity=ast_similarity,
        ),
        "kind": "shadow-implementation",
        "level": "caution",
        "confidence": confidence,
        "location": {
            "path": duplicate.path,
            "line": duplicate.line,
            "symbol": duplicate.symbol,
            "symbol_kind": duplicate.symbol_kind,
        },
        "root_cause": "Function appears similar to an existing implementation without a direct reuse edge.",
        "evidence": evidence,
        "references": [
            {
                "role": "existing_implementation",
                "path": existing.path,
                "line": existing.line,
                "symbol": existing.symbol,
                "symbol_kind": existing.symbol_kind,
            }
        ],
        "blast_radius": [duplicate.path, existing.path],
        "next_steps_hint": "Review whether the implementations should share an existing entry point or stay explicitly separate.",
    }


def _shadow_pair(left: _FunctionCandidate, right: _FunctionCandidate) -> dict[str, Any] | None:
    if left.path == right.path:
        return None
    if left.fingerprint == right.fingerprint:
        return None
    common_roles = left.role_tokens & right.role_tokens
    if not common_roles:
        return None
    name_overlap = _jaccard(left.name_tokens, right.name_tokens)
    if name_overlap < MIN_NAME_OVERLAP:
        return None
    signature_similarity = _signature_similarity(left, right)
    if signature_similarity < MIN_SIGNATURE_SIMILARITY:
        return None
    ast_similarity = _cosine(left.feature_vector, right.feature_vector)
    if ast_similarity < MIN_AST_SIMILARITY:
        return None
    if _has_reuse_edge(left, right) or _has_reuse_edge(right, left):
        return None
    role = _primary_role(common_roles)
    if _confidence(name_overlap, signature_similarity, ast_similarity) < MIN_CONFIDENCE:
        return None
    return _build_concern(
        left,
        right,
        role=role,
        name_overlap=name_overlap,
        signature_similarity=signature_similarity,
        ast_similarity=ast_similarity,
    )


def shadow_implementation_concerns(
    project_root: str | Path,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    root = Path(project_root)
    candidates: list[_FunctionCandidate] = []
    for path in _iter_python_files(root):
        candidates.extend(_collect_functions(path, root))

    concerns: list[dict[str, Any]] = []
    for left, right in combinations(sorted(candidates, key=_candidate_key), 2):
        concern = _shadow_pair(left, right)
        if concern is not None:
            concerns.append(concern)

    return sorted(
        concerns,
        key=lambda item: (
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("location", {}).get("path", "") if isinstance(item.get("location"), dict) else ""),
            str(item.get("concern_id", "") or ""),
        ),
    )[:limit]


__all__ = ["shadow_implementation_concerns"]
