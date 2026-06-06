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
from typing import Any, Iterable

from architec.code_review.scan_cache import collect_file_scan_cache


SKIP_DIRS = {
    ".architec",
    ".cache",
    ".ccb",
    ".git",
    ".hippos",
    ".hippocampus",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "benchmark",
    "benchmarks",
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
MODULE_SPLIT_TOKENS = {
    "helper",
    "helpers",
    "payload",
    "registry",
    "runtime",
    "section",
    "sections",
    "support",
    "view",
    "views",
}
RENDER_ROLE_TOKENS = {"render", "renderer", "rendering"}
ASSEMBLY_ROLE_TOKENS = {"append", "assemble", "assembler", "assembly", "budget", "context", "support"}
VISUAL_MAPPER_TOKENS = {
    "badge",
    "color",
    "colors",
    "colour",
    "colours",
    "display",
    "displays",
    "hue",
    "legend",
    "palette",
    "render",
    "rendering",
    "role",
    "roles",
    "shade",
    "style",
    "styles",
    "theme",
    "tier",
    "tiers",
    "visual",
    "visualization",
}
MIGRATION_MAPPER_TOKENS = {
    "alias",
    "aliases",
    "compat",
    "compatibility",
    "compatible",
    "diff",
    "from",
    "legacy",
    "migrate",
    "migrated",
    "migrates",
    "migration",
    "migrations",
    "move",
    "moves",
    "moved",
    "new",
    "old",
    "rename",
    "renamed",
    "renames",
    "source",
    "sources",
    "target",
    "targets",
    "to",
}
RUNTIME_PARSER_TOKENS = {
    "glibc",
    "libc",
    "manylinux",
    "musl",
    "musllinux",
    "platform",
    "runtime",
}
LOCAL_VERSION_PARSER_TOKENS = {
    "local",
    "locals",
}
VERSION_GRAMMAR_PARSER_TOKENS = {
    "grammar",
    "many",
    "marker",
    "markers",
    "requirement",
    "requirements",
    "specifier",
    "specifiers",
    "token",
    "tokens",
}
VERSION_PARSER_TOKENS = {
    "version",
    "versions",
}

MIN_NODE_COUNT = 45
MIN_CLASS_NODE_COUNT = 90
MIN_MODULE_NODE_COUNT = 220
MIN_MODULE_PUBLIC_SYMBOLS = 5
MIN_MODULE_API_OVERLAP = 0.55
MIN_MODULE_SHAPE_SIMILARITY = 0.65
MIN_MODULE_AST_SIMILARITY = 0.88
MIN_MODULE_IMPORT_SIMILARITY = 0.45
MIN_NAME_OVERLAP = 0.45
MIN_SIGNATURE_SIMILARITY = 0.6
MIN_CLASS_API_SIMILARITY = 0.6
MIN_AST_SIMILARITY = 0.82
MIN_CONFIDENCE = 0.78
SCAN_CACHE_VERSION = 1
SCAN_CACHE_PATH = Path(".architec/cache/code-review-shadow-implementation-index.json")


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
    api_tokens: frozenset[str] = frozenset()
    member_tokens: frozenset[str] = frozenset()
    member_count: int = 0

    @property
    def module_tokens(self) -> frozenset[str]:
        return frozenset(_tokens(Path(self.path).stem))


@dataclass(frozen=True)
class _ShadowMatch:
    role: str
    name_overlap: float
    signature_similarity: float
    ast_similarity: float


@dataclass(frozen=True)
class _ModuleCandidate:
    path: str
    node_count: int
    public_symbol_count: int
    role_tokens: frozenset[str]
    public_api_tokens: frozenset[str]
    symbol_shape_tokens: frozenset[str]
    feature_vector: dict[str, float]
    imports: frozenset[str]
    names: frozenset[str]
    calls: frozenset[str]
    attrs: frozenset[str]


class _NormalizeAst(ast.NodeTransformer):
    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:  # noqa: N802
        node.name = "_class"
        self.generic_visit(node)
        return node

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


def _has_pure_role(tokens: frozenset[str], positive: set[str], negative: set[str]) -> bool:
    return bool(tokens & positive) and not bool(tokens & negative)


def _has_intentional_split_role_pair(left: _FunctionCandidate, right: _FunctionCandidate) -> bool:
    left_render = _has_pure_role(left.all_tokens, RENDER_ROLE_TOKENS, ASSEMBLY_ROLE_TOKENS)
    right_render = _has_pure_role(right.all_tokens, RENDER_ROLE_TOKENS, ASSEMBLY_ROLE_TOKENS)
    left_assembly = _has_pure_role(left.all_tokens, ASSEMBLY_ROLE_TOKENS, RENDER_ROLE_TOKENS)
    right_assembly = _has_pure_role(right.all_tokens, ASSEMBLY_ROLE_TOKENS, RENDER_ROLE_TOKENS)
    return (left_render and right_assembly) or (right_render and left_assembly)


def _raw_candidate_tokens(candidate: _FunctionCandidate) -> frozenset[str]:
    return frozenset([*_tokens(candidate.symbol), *_tokens(candidate.path)])


def _mapper_subdomain(candidate: _FunctionCandidate) -> str:
    if "mapper" not in candidate.role_tokens:
        return ""
    tokens = _raw_candidate_tokens(candidate)
    visual = bool(tokens & VISUAL_MAPPER_TOKENS)
    migration = bool(tokens & MIGRATION_MAPPER_TOKENS)
    if visual and not migration:
        return "visual"
    if migration and not visual:
        return "migration"
    return ""


def _has_mapper_subdomain_split(left: _FunctionCandidate, right: _FunctionCandidate) -> bool:
    left_subdomain = _mapper_subdomain(left)
    right_subdomain = _mapper_subdomain(right)
    return {left_subdomain, right_subdomain} == {"visual", "migration"}


def _parser_subdomain(candidate: _FunctionCandidate) -> str:
    if "parser" not in candidate.role_tokens:
        return ""
    tokens = _raw_candidate_tokens(candidate)
    runtime = bool(tokens & RUNTIME_PARSER_TOKENS)
    local = bool(tokens & LOCAL_VERSION_PARSER_TOKENS)
    grammar = bool(tokens & VERSION_GRAMMAR_PARSER_TOKENS)
    version = bool(tokens & VERSION_PARSER_TOKENS)
    if runtime and not local and not grammar:
        return "runtime"
    if local and not runtime and not grammar:
        return "local_version"
    if (grammar or version) and not runtime and not local:
        return "version_grammar"
    return ""


def _has_parser_subdomain_split(left: _FunctionCandidate, right: _FunctionCandidate) -> bool:
    left_subdomain = _parser_subdomain(left)
    right_subdomain = _parser_subdomain(right)
    return bool(left_subdomain and right_subdomain and left_subdomain != right_subdomain)


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


def _class_api_similarity(left: _FunctionCandidate, right: _FunctionCandidate) -> float:
    largest = max(left.member_count, right.member_count, 1)
    member_count_similarity = 1.0 - (abs(left.member_count - right.member_count) / largest)
    api_similarity = _jaccard(left.api_tokens, right.api_tokens)
    member_similarity = _jaccard(left.member_tokens, right.member_tokens)
    return (0.45 * api_similarity) + (0.35 * member_similarity) + (0.2 * member_count_similarity)


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


def _class_members(node: ast.ClassDef) -> tuple[frozenset[str], frozenset[str], int, frozenset[str], int]:
    api_tokens: set[str] = set()
    member_tokens: set[str] = set()
    initializer_tokens: frozenset[str] = frozenset()
    initializer_count = 0
    member_count = 0
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if child.name.startswith("__") and child.name != "__init__":
                continue
            member_count += 1
            method_tokens = _meaningful_tokens(child.name)
            api_tokens.update(method_tokens)
            member_tokens.update(method_tokens)
            signature_tokens, parameter_count = _signature_tokens(child)
            member_tokens.update(signature_tokens)
            if child.name == "__init__":
                initializer_tokens = signature_tokens
                initializer_count = parameter_count
        elif isinstance(child, (ast.Assign, ast.AnnAssign)):
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    member_tokens.update(_meaningful_tokens(target.id))
                elif isinstance(target, ast.Attribute):
                    member_tokens.update(_meaningful_tokens(target.attr))
    return (
        frozenset(api_tokens),
        frozenset(member_tokens),
        member_count,
        initializer_tokens,
        initializer_count,
    )


def _collect_classes(path: Path, root: Path) -> list[_FunctionCandidate]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    relpath = path.relative_to(root).as_posix()
    imports = _module_imports(tree)
    found: list[_FunctionCandidate] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.class_depth = 0

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
            if self.class_depth:
                return
            self.class_depth += 1
            try:
                size = _node_count(node)
                if size < MIN_CLASS_NODE_COUNT:
                    return
                symbol_tokens = _meaningful_tokens(node.name)
                path_tokens = _meaningful_tokens(relpath)
                all_tokens = set(symbol_tokens) | set(path_tokens)
                if _is_adapter_like(all_tokens):
                    return
                roles = _role_tokens(all_tokens)
                if not roles:
                    return
                api_tokens, member_tokens, member_count, initializer_tokens, initializer_count = _class_members(node)
                if member_count < 2:
                    return
                names, calls, attrs = _references(node)
                found.append(
                    _FunctionCandidate(
                        path=relpath,
                        line=int(getattr(node, "lineno", 0) or 0),
                        symbol=node.name,
                        symbol_kind="class",
                        node_count=size,
                        fingerprint=_fingerprint(node),
                        name_tokens=symbol_tokens,
                        all_tokens=frozenset(all_tokens),
                        role_tokens=roles,
                        signature_tokens=initializer_tokens,
                        parameter_count=initializer_count,
                        feature_vector=_feature_vector(node),
                        names=names,
                        calls=calls,
                        attrs=attrs,
                        imports=imports,
                        api_tokens=api_tokens,
                        member_tokens=member_tokens,
                        member_count=member_count,
                    )
                )
            finally:
                self.class_depth -= 1

    Visitor().visit(tree)
    return found


def _sorted_strings(values: Iterable[str]) -> list[str]:
    return sorted(str(value) for value in values)


def _candidate_to_json(item: _FunctionCandidate) -> dict[str, Any]:
    return {
        "path": item.path,
        "line": item.line,
        "symbol": item.symbol,
        "symbol_kind": item.symbol_kind,
        "node_count": item.node_count,
        "fingerprint": item.fingerprint,
        "name_tokens": _sorted_strings(item.name_tokens),
        "all_tokens": _sorted_strings(item.all_tokens),
        "role_tokens": _sorted_strings(item.role_tokens),
        "signature_tokens": _sorted_strings(item.signature_tokens),
        "parameter_count": item.parameter_count,
        "feature_vector": dict(item.feature_vector),
        "names": _sorted_strings(item.names),
        "calls": _sorted_strings(item.calls),
        "attrs": _sorted_strings(item.attrs),
        "imports": _sorted_strings(item.imports),
        "api_tokens": _sorted_strings(item.api_tokens),
        "member_tokens": _sorted_strings(item.member_tokens),
        "member_count": item.member_count,
    }


def _candidate_from_json(data: object) -> _FunctionCandidate | None:
    if not isinstance(data, dict):
        return None
    try:
        return _FunctionCandidate(
            path=str(data.get("path", "") or ""),
            line=int(data.get("line", 0) or 0),
            symbol=str(data.get("symbol", "") or ""),
            symbol_kind=str(data.get("symbol_kind", "") or "function"),
            node_count=int(data.get("node_count", 0) or 0),
            fingerprint=str(data.get("fingerprint", "") or ""),
            name_tokens=frozenset(str(item) for item in data.get("name_tokens", []) if str(item or "").strip()),
            all_tokens=frozenset(str(item) for item in data.get("all_tokens", []) if str(item or "").strip()),
            role_tokens=frozenset(str(item) for item in data.get("role_tokens", []) if str(item or "").strip()),
            signature_tokens=frozenset(
                str(item) for item in data.get("signature_tokens", []) if str(item or "").strip()
            ),
            parameter_count=int(data.get("parameter_count", 0) or 0),
            feature_vector={
                str(key): float(value)
                for key, value in (data.get("feature_vector", {}) or {}).items()
            },
            names=frozenset(str(item) for item in data.get("names", []) if str(item or "").strip()),
            calls=frozenset(str(item) for item in data.get("calls", []) if str(item or "").strip()),
            attrs=frozenset(str(item) for item in data.get("attrs", []) if str(item or "").strip()),
            imports=frozenset(str(item) for item in data.get("imports", []) if str(item or "").strip()),
            api_tokens=frozenset(str(item) for item in data.get("api_tokens", []) if str(item or "").strip()),
            member_tokens=frozenset(str(item) for item in data.get("member_tokens", []) if str(item or "").strip()),
            member_count=int(data.get("member_count", 0) or 0),
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _collect_candidates_cached(root: Path) -> tuple[list[_FunctionCandidate], dict[str, int]]:
    def collect_file(path: Path, project_root: Path) -> list[_FunctionCandidate]:
        return [*_collect_functions(path, project_root), *_collect_classes(path, project_root)]

    return collect_file_scan_cache(
        root,
        cache_path=SCAN_CACHE_PATH,
        version=SCAN_CACHE_VERSION,
        python_files=_iter_python_files(root),
        collect_file=collect_file,
        encode_item=_candidate_to_json,
        decode_item=_candidate_from_json,
    )


def _public_top_level_symbols(tree: ast.Module) -> tuple[list[ast.AST], frozenset[str], frozenset[str]]:
    nodes: list[ast.AST] = []
    api_tokens: set[str] = set()
    shape_tokens: set[str] = set()
    for child in tree.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = child.name
            if name.startswith("_"):
                continue
            nodes.append(child)
            tokens = _meaningful_tokens(name)
            api_tokens.update(tokens)
            kind = "class" if isinstance(child, ast.ClassDef) else "function"
            shape_tokens.add(kind)
            shape_tokens.update(f"{kind}:{token}" for token in tokens)
    return nodes, frozenset(api_tokens), frozenset(shape_tokens)


def _module_candidate(path: Path, root: Path) -> tuple[_ModuleCandidate | None, str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None, "parse_error"
    relpath = path.relative_to(root).as_posix()
    nodes, public_api_tokens, symbol_shape_tokens = _public_top_level_symbols(tree)
    public_symbol_count = len(nodes)
    node_count = _node_count(tree)
    if node_count < MIN_MODULE_NODE_COUNT and public_symbol_count < MIN_MODULE_PUBLIC_SYMBOLS:
        return None, "too_small"
    path_tokens = _meaningful_tokens(relpath)
    all_tokens = set(path_tokens) | set(public_api_tokens)
    if _is_adapter_like(all_tokens):
        return None, "adapter_like"
    if all_tokens & MODULE_SPLIT_TOKENS:
        return None, "split_module_name"
    roles = _role_tokens(all_tokens)
    if not roles:
        return None, "no_role"
    names, calls, attrs = _references(tree)
    return (
        _ModuleCandidate(
            path=relpath,
            node_count=node_count,
            public_symbol_count=public_symbol_count,
            role_tokens=roles,
            public_api_tokens=public_api_tokens,
            symbol_shape_tokens=symbol_shape_tokens,
            feature_vector=_feature_vector(tree),
            imports=_module_imports(tree),
            names=names,
            calls=calls,
            attrs=attrs,
        ),
        "",
    )


def _collect_module_candidates(root: Path) -> tuple[list[_ModuleCandidate], dict[str, int]]:
    candidates: list[_ModuleCandidate] = []
    by_exclusion: dict[str, int] = {}
    for path in _iter_python_files(root):
        candidate, reason = _module_candidate(path, root)
        if candidate is None:
            by_exclusion[reason] = by_exclusion.get(reason, 0) + 1
            continue
        candidates.append(candidate)
    return candidates, by_exclusion


def _has_reuse_edge(source: _FunctionCandidate, target: _FunctionCandidate) -> bool:
    target_leaf = target.symbol.rsplit(".", 1)[-1].lower()
    target_tokens = {
        target.symbol.lower(),
        target_leaf,
        Path(target.path).stem.lower(),
    }
    references = set(source.calls) | set(source.attrs) | set(source.names) | set(source.imports)
    return bool(target_tokens & references)


def _module_has_reuse_edge(source: _ModuleCandidate, target: _ModuleCandidate) -> bool:
    target_stem = Path(target.path).stem.lower()
    target_tokens = set(_tokens(target_stem))
    references = set(source.imports) | set(source.names) | set(source.calls) | set(source.attrs)
    return bool({target_stem, *target_tokens} & references)


def _module_shape_similarity(left: _ModuleCandidate, right: _ModuleCandidate) -> float:
    largest = max(left.public_symbol_count, right.public_symbol_count, 1)
    count_similarity = 1.0 - (abs(left.public_symbol_count - right.public_symbol_count) / largest)
    shape_similarity = _jaccard(left.symbol_shape_tokens, right.symbol_shape_tokens)
    return (0.7 * shape_similarity) + (0.3 * count_similarity)


def _module_pair_summary(left: _ModuleCandidate, right: _ModuleCandidate) -> dict[str, Any] | None:
    if left.path == right.path:
        return None
    common_roles = left.role_tokens & right.role_tokens
    if not common_roles:
        return None
    api_overlap = _jaccard(left.public_api_tokens, right.public_api_tokens)
    if api_overlap < MIN_MODULE_API_OVERLAP:
        return None
    shape_similarity = _module_shape_similarity(left, right)
    if shape_similarity < MIN_MODULE_SHAPE_SIMILARITY:
        return None
    ast_similarity = _cosine(left.feature_vector, right.feature_vector)
    if ast_similarity < MIN_MODULE_AST_SIMILARITY:
        return None
    import_similarity = _jaccard(left.imports, right.imports)
    if import_similarity < MIN_MODULE_IMPORT_SIMILARITY:
        return None
    if _module_has_reuse_edge(left, right) or _module_has_reuse_edge(right, left):
        return None
    role = _primary_role(common_roles)
    return {
        "left": {
            "path": left.path,
            "node_count": left.node_count,
            "public_symbol_count": left.public_symbol_count,
        },
        "right": {
            "path": right.path,
            "node_count": right.node_count,
            "public_symbol_count": right.public_symbol_count,
        },
        "role": role,
        "metrics": {
            "public_api_overlap": round(api_overlap, 3),
            "symbol_shape_similarity": round(shape_similarity, 3),
            "ast_similarity": round(ast_similarity, 3),
            "import_similarity": round(import_similarity, 3),
        },
        "reason": "module-level shadow candidate for dry-run calibration",
        "facts": [
            f"shadow_implementation.file.role={role}",
            "shadow_implementation.file.reuse_edge=false",
            f"shadow_implementation.file.node_counts={left.node_count}/{right.node_count}",
            f"shadow_implementation.file.public_symbol_counts={left.public_symbol_count}/{right.public_symbol_count}",
        ],
    }


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


def _class_confidence(name_overlap: float, api_similarity: float, ast_similarity: float) -> float:
    confidence = (
        0.78
        + max(ast_similarity - MIN_AST_SIMILARITY, 0.0) * 0.4
        + max(api_similarity - MIN_CLASS_API_SIMILARITY, 0.0) * 0.25
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
        "scope": duplicate.symbol_kind,
        "duplicate": {
            "path": duplicate.path,
            "line": duplicate.line,
            "symbol": duplicate.symbol,
            "symbol_kind": duplicate.symbol_kind,
        },
        "existing": {
            "path": existing.path,
            "line": existing.line,
            "symbol": existing.symbol,
            "symbol_kind": existing.symbol_kind,
        },
        "role": role,
        "name_overlap": round(name_overlap, 4),
        "ast_similarity": round(ast_similarity, 4),
    }
    if duplicate.symbol_kind == "class":
        payload["api_similarity"] = round(signature_similarity, 4)
        payload["member_counts"] = [duplicate.member_count, existing.member_count]
    else:
        payload["signature_similarity"] = round(signature_similarity, 4)
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
    primary: _FunctionCandidate | None = None,
) -> dict[str, Any]:
    if primary is left:
        existing, duplicate = right, left
    elif primary is right:
        existing, duplicate = left, right
    else:
        existing, duplicate = sorted([left, right], key=_candidate_key)
    if duplicate.symbol_kind == "class":
        confidence = _class_confidence(name_overlap, signature_similarity, ast_similarity)
        evidence = [
            "shadow_implementation.scope=class",
            f"shadow_implementation.name_overlap={name_overlap:.2f}",
            f"shadow_implementation.api_similarity={signature_similarity:.2f}",
            f"shadow_implementation.ast_similarity={ast_similarity:.2f}",
            f"shadow_implementation.role={role}",
            "shadow_implementation.reuse_edge=false",
            f"shadow_implementation.node_counts={duplicate.node_count}/{existing.node_count}",
            f"shadow_implementation.member_counts={duplicate.member_count}/{existing.member_count}",
        ]
        root_cause = "Class appears similar to an existing implementation without a direct reuse edge."
    else:
        confidence = _confidence(name_overlap, signature_similarity, ast_similarity)
        evidence = [
            f"shadow_implementation.name_overlap={name_overlap:.2f}",
            f"shadow_implementation.signature_similarity={signature_similarity:.2f}",
            f"shadow_implementation.ast_similarity={ast_similarity:.2f}",
            f"shadow_implementation.role={role}",
            "shadow_implementation.reuse_edge=false",
            f"shadow_implementation.node_counts={duplicate.node_count}/{existing.node_count}",
        ]
        root_cause = "Function appears similar to an existing implementation without a direct reuse edge."
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
        "root_cause": root_cause,
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


def _shadow_match(left: _FunctionCandidate, right: _FunctionCandidate) -> _ShadowMatch | None:
    if left.path == right.path:
        return None
    if left.symbol_kind != right.symbol_kind:
        return None
    if left.fingerprint == right.fingerprint:
        return None
    common_roles = left.role_tokens & right.role_tokens
    if not common_roles:
        return None
    if _has_intentional_split_role_pair(left, right):
        return None
    if _has_mapper_subdomain_split(left, right):
        return None
    if _has_parser_subdomain_split(left, right):
        return None
    name_overlap = _jaccard(left.name_tokens, right.name_tokens)
    if name_overlap < MIN_NAME_OVERLAP:
        return None
    if left.symbol_kind == "class":
        signature_similarity = _class_api_similarity(left, right)
        if signature_similarity < MIN_CLASS_API_SIMILARITY:
            return None
    else:
        signature_similarity = _signature_similarity(left, right)
        if signature_similarity < MIN_SIGNATURE_SIMILARITY:
            return None
    ast_similarity = _cosine(left.feature_vector, right.feature_vector)
    if ast_similarity < MIN_AST_SIMILARITY:
        return None
    if _has_reuse_edge(left, right) or _has_reuse_edge(right, left):
        return None
    role = _primary_role(common_roles)
    confidence = (
        _class_confidence(name_overlap, signature_similarity, ast_similarity)
        if left.symbol_kind == "class"
        else _confidence(name_overlap, signature_similarity, ast_similarity)
    )
    if confidence < MIN_CONFIDENCE:
        return None
    return _ShadowMatch(
        role=role,
        name_overlap=name_overlap,
        signature_similarity=signature_similarity,
        ast_similarity=ast_similarity,
    )


def _changed_primary(
    left: _FunctionCandidate,
    right: _FunctionCandidate,
    changed_files: frozenset[str] | None,
) -> _FunctionCandidate | None:
    if changed_files is None:
        return None
    left_changed = left.path in changed_files
    right_changed = right.path in changed_files
    if left_changed and not right_changed:
        return left
    if right_changed and not left_changed:
        return right
    if left_changed and right_changed:
        return None
    return None


def _shadow_pair(
    left: _FunctionCandidate,
    right: _FunctionCandidate,
    *,
    changed_files: frozenset[str] | None = None,
) -> dict[str, Any] | None:
    match = _shadow_match(left, right)
    if match is None:
        return None
    if changed_files is not None and left.path not in changed_files and right.path not in changed_files:
        return None
    return _build_concern(
        left,
        right,
        role=match.role,
        name_overlap=match.name_overlap,
        signature_similarity=match.signature_similarity,
        ast_similarity=match.ast_similarity,
        primary=_changed_primary(left, right, changed_files),
    )


def _normalized_changed_files(changed_files: Iterable[str] | None) -> frozenset[str] | None:
    if changed_files is None:
        return None
    normalized = {
        Path(str(path)).as_posix().lstrip("./")
        for path in changed_files
        if str(path or "").strip()
    }
    return frozenset(normalized)


def shadow_implementation_scan(
    project_root: str | Path,
    *,
    limit: int = 20,
    changed_files: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root)
    changed_scope = _normalized_changed_files(changed_files)
    candidates, scan_cache = _collect_candidates_cached(root)

    candidate_total_before_scope = 0
    concerns: list[dict[str, Any]] = []
    for left, right in combinations(sorted(candidates, key=_candidate_key), 2):
        match = _shadow_match(left, right)
        if match is None:
            continue
        candidate_total_before_scope += 1
        if changed_scope is not None and left.path not in changed_scope and right.path not in changed_scope:
            continue
        concerns.append(
            _build_concern(
                left,
                right,
                role=match.role,
                name_overlap=match.name_overlap,
                signature_similarity=match.signature_similarity,
                ast_similarity=match.ast_similarity,
                primary=_changed_primary(left, right, changed_scope),
            )
        )

    sorted_concerns = sorted(
        concerns,
        key=lambda item: (
            -float(item.get("confidence", 0.0) or 0.0),
            str(item.get("location", {}).get("path", "") if isinstance(item.get("location"), dict) else ""),
            str(item.get("concern_id", "") or ""),
        ),
    )[:limit]
    result: dict[str, Any] = {
        "concerns": sorted_concerns,
        "candidate_total_before_scope": candidate_total_before_scope,
        "scan_cache": scan_cache,
    }
    if changed_scope is not None:
        result["scoped_to_changed_files"] = True
        result["changed_file_total"] = len(changed_scope)
    return result


def shadow_implementation_concerns(
    project_root: str | Path,
    *,
    limit: int = 20,
    changed_files: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    return list(
        shadow_implementation_scan(
            project_root,
            limit=limit,
            changed_files=changed_files,
        )["concerns"]
    )


def shadow_implementation_file_dry_run(
    project_root: str | Path,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    root = Path(project_root)
    candidates, by_exclusion = _collect_module_candidates(root)
    pairs: list[dict[str, Any]] = []
    for left, right in combinations(sorted(candidates, key=lambda item: item.path), 2):
        summary = _module_pair_summary(left, right)
        if summary is not None:
            pairs.append(summary)
    sorted_pairs = sorted(
        pairs,
        key=lambda item: (
            -float(
                item.get("metrics", {}).get("ast_similarity", 0.0)
                if isinstance(item.get("metrics"), dict)
                else 0.0
            ),
            str(item.get("left", {}).get("path", "") if isinstance(item.get("left"), dict) else ""),
            str(item.get("right", {}).get("path", "") if isinstance(item.get("right"), dict) else ""),
        ),
    )
    return {
        "mode": "dry_run",
        "candidate_total": len(candidates),
        "pair_total": len(pairs),
        "reported_total": min(len(pairs), limit),
        "candidates": sorted_pairs[:limit],
        "excluded_total": sum(by_exclusion.values()),
        "by_exclusion": dict(sorted(by_exclusion.items())),
    }


__all__ = [
    "shadow_implementation_concerns",
    "shadow_implementation_file_dry_run",
    "shadow_implementation_scan",
]
