from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from architec.support.architecture_rules import ArchitectureRules, load_archi_rules, path_is_ignored
from architec.support.io_utils import normalize_relpath
from architec.support.path_policy import path_kind

_SCRIPT_SUFFIXES = {
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
}
_SCRIPT_DIRS = {"script", "scripts", "tools", "bin"}
_CONFIG_SUFFIXES = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".properties",
    ".env",
}
_CONFIG_NAMES = {
    "dockerfile",
    "compose.yaml",
    "compose.yml",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "cargo.toml",
    "go.mod",
    "go.sum",
}
_PROMPT_DIRS = {"prompt", "prompts"}
_PROMPT_SUFFIXES = {".prompt"}


@dataclass(frozen=True)
class CleanupScopeEntry:
    path: str
    kind: str


def _parts(path: str) -> list[str]:
    return [part for part in normalize_relpath(path).split("/") if part]


def _is_prompt_path(path: str) -> bool:
    parts = _parts(path)
    if not parts:
        return False
    suffix = Path(parts[-1]).suffix.lower()
    normalized_dirs = {part.lower() for part in parts[:-1]}
    if suffix in _PROMPT_SUFFIXES:
        return True
    return bool(normalized_dirs & _PROMPT_DIRS)


def _is_config_path(path: str) -> bool:
    parts = _parts(path)
    if not parts:
        return False
    name = parts[-1].lower()
    suffix = Path(name).suffix.lower()
    if name in _CONFIG_NAMES:
        return True
    return suffix in _CONFIG_SUFFIXES


def _is_script_path(path: str) -> bool:
    parts = _parts(path)
    if not parts:
        return False
    name = parts[-1].lower()
    suffix = Path(name).suffix.lower()
    normalized_dirs = {part.lower() for part in parts[:-1]}
    if suffix in _SCRIPT_SUFFIXES:
        return True
    return bool(normalized_dirs & _SCRIPT_DIRS) and suffix in {".py", ".rb", ".pl", ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd"}


def classify_cleanup_path(
    path: str | Path,
    *,
    rules: ArchitectureRules | None = None,
) -> str | None:
    normalized = normalize_relpath(str(path or ""))
    if not normalized or path_is_ignored(normalized, rules):
        return None
    base_kind = path_kind(normalized)
    if base_kind in {"hidden", "excluded", "fixture", "generated", "infra", "test"}:
        return None
    if _is_prompt_path(normalized):
        return "prompt"
    if _is_config_path(normalized):
        return "config"
    if _is_script_path(normalized):
        return "script"
    if base_kind == "doc":
        return "doc"
    if base_kind == "source":
        return "source"
    return None


def iter_cleanup_scope(
    project_root: str | Path,
    *,
    rules: ArchitectureRules | None = None,
) -> list[CleanupScopeEntry]:
    root = Path(project_root).resolve()
    effective_rules = rules or load_archi_rules(root)
    allowed_kinds = {"source", *effective_rules.cleanup_extra_kinds}
    entries: list[CleanupScopeEntry] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = normalize_relpath(path.relative_to(root))
        kind = classify_cleanup_path(rel, rules=effective_rules)
        if not kind or kind not in allowed_kinds:
            continue
        entries.append(CleanupScopeEntry(path=rel, kind=kind))
    return entries
