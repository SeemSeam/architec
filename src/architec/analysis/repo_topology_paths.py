from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from ..integration.hippo_adapter import HippoSnapshot
from ..support.io_utils import clamp, normalize_relpath


def python_files(snapshot: HippoSnapshot) -> list[str]:
    return [
        path
        for path in snapshot.first_party_paths()
        if path.endswith(".py") and "__pycache__" not in path
    ]


def candidate_source_roots(paths: list[str]) -> dict[str, list[str]]:
    roots: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        norm = normalize_relpath(path)
        parts = [part for part in norm.split("/") if part]
        if len(parts) >= 3 and parts[0] == "src":
            roots["/".join(parts[:2])].append(norm)
            continue
        if len(parts) >= 2:
            roots[parts[0]].append(norm)
    return roots


def source_root(paths: list[str]) -> str:
    candidates = candidate_source_roots(paths)
    if not candidates:
        return ""
    ranked = sorted(candidates.items(), key=lambda item: (-len(item[1]), item[0]))
    return ranked[0][0]


def direct_module_paths(paths: list[str], source_root: str) -> list[str]:
    root = normalize_relpath(source_root).rstrip("/")
    if not root:
        return []
    prefix = f"{root}/"
    direct: list[str] = []
    for path in paths:
        if not path.startswith(prefix):
            continue
        rel = path[len(prefix):]
        if "/" in rel:
            continue
        if not rel.endswith(".py"):
            continue
        if rel.startswith("_") and rel not in {"__init__.py", "__main__.py"}:
            continue
        direct.append(path)
    return sorted(direct)


def compat_wrapper_paths(project_root: Path, direct_files: list[str]) -> list[str]:
    wrappers: list[str] = []
    for path in direct_files:
        abs_path = project_root / normalize_relpath(path)
        try:
            text = abs_path.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        body = list(tree.body)
        if len(body) < 2:
            continue
        import_node = body[0]
        call_node = body[1]
        if not isinstance(import_node, ast.ImportFrom):
            continue
        if import_node.level != 1 or import_node.module != "_compat_reexport":
            continue
        if [alias.name for alias in import_node.names] != ["reexport"]:
            continue
        if not isinstance(call_node, ast.Expr) or not isinstance(call_node.value, ast.Call):
            continue
        func = call_node.value.func
        if not isinstance(func, ast.Name) or func.id != "reexport":
            continue
        if any(not isinstance(node, (ast.ImportFrom, ast.Expr)) for node in body):
            continue
        if any(
            isinstance(node, ast.Expr)
            and (
                not isinstance(node.value, ast.Call)
                or not isinstance(node.value.func, ast.Name)
                or node.value.func.id != "reexport"
            )
            for node in body[1:]
        ):
            continue
        wrappers.append(path)
    return sorted(wrappers)


def peer_directories(source_root: str, project_root: Path) -> list[str]:
    root = project_root / source_root
    if not root.exists() or not root.is_dir():
        return []
    peers = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.name.startswith((".", "__")):
            peers.append(child.name)
    return peers[:12]


def flatness_score(flat_file_total: int, subpackage_total: int, grouped_total: int) -> float:
    penalty = 0.0
    if flat_file_total > 10:
        penalty += min(45.0, (flat_file_total - 10) * 1.2)
    if subpackage_total == 0 and flat_file_total >= 12:
        penalty += 18.0
    if grouped_total <= 2 and flat_file_total >= 18:
        penalty += 12.0
    return round(clamp(100.0 - penalty, 0.0, 100.0), 2)
