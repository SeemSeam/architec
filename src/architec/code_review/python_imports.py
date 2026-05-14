from __future__ import annotations

import ast
from dataclasses import dataclass

from fnmatch import fnmatchcase

from architec.support.io_utils import normalize_relpath


@dataclass(frozen=True)
class ImportRecord:
    module: str
    line: int


def _normal_path(path: object) -> str:
    text = normalize_relpath(str(path or ""))
    while text.startswith("./"):
        text = text[2:]
    return text.strip("/")


def module_matches(module: str, pattern: str) -> bool:
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


def import_records(path: str, source: str) -> list[ImportRecord]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    records: list[ImportRecord] = []
    seen: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = str(alias.name or "").strip()
                key = (module, int(getattr(node, "lineno", 0) or 0))
                if module and key not in seen:
                    seen.add(key)
                    records.append(ImportRecord(module=module, line=key[1]))
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
                    records.append(ImportRecord(module=item, line=line))
    return records


__all__ = ["ImportRecord", "import_records", "module_matches"]
