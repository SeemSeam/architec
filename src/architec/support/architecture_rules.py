from __future__ import annotations

from datetime import date, datetime, timezone
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from .io_utils import normalize_relpath


RULES_FILE_NAME = ".architecture-rules.toml"


@dataclass(frozen=True)
class CleanupMetadataRule:
    path: str = ""
    glob: str = ""
    kind: str = ""
    category: str = ""
    owner: str = ""
    ttl_days: int | None = None
    expires_at: str = ""


@dataclass(frozen=True)
class ArchitectureRules:
    ignore_paths: tuple[str, ...] = ()
    ignore_globs: tuple[str, ...] = ()
    ignore_extensions: tuple[str, ...] = ()
    cleanup_extra_kinds: tuple[str, ...] = ("doc", "config", "prompt", "script")
    cleanup_metadata_rules: tuple[CleanupMetadataRule, ...] = ()


def _string_list(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = normalize_relpath(str(item or ""))
        while text.startswith("./"):
            text = text[2:]
        text = text.rstrip("/")
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return tuple(values)


def _extension_list(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    values: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item or "").strip().lower()
        if not text:
            continue
        if not text.startswith("."):
            text = f".{text}"
        if text in seen:
            continue
        seen.add(text)
        values.append(text)
    return tuple(values)


def _normalized_relpath_text(raw: object) -> str:
    text = normalize_relpath(str(raw or ""))
    while text.startswith("./"):
        text = text[2:]
    return text.rstrip("/")


def _normalized_text(raw: object) -> str:
    return str(raw or "").strip()


def _normalized_optional_int(raw: object) -> int | None:
    try:
        value = int(raw)
    except Exception:
        return None
    return value if value > 0 else None


def _normalized_expires_at(raw: object) -> str:
    text = _normalized_text(raw)
    if not text:
        return ""
    probe = text
    if probe.endswith("Z"):
        probe = probe[:-1] + "+00:00"
    try:
        datetime.fromisoformat(probe)
        return text
    except ValueError:
        pass
    try:
        date.fromisoformat(probe)
        return text
    except ValueError:
        return ""


def _cleanup_metadata_rules(raw: object) -> tuple[CleanupMetadataRule, ...]:
    if not isinstance(raw, list):
        return ()
    rules: list[CleanupMetadataRule] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        path = _normalized_relpath_text(item.get("path", ""))
        glob = _normalized_relpath_text(item.get("glob", ""))
        if not path and not glob:
            continue
        owner = _normalized_text(item.get("owner", ""))
        ttl_days = _normalized_optional_int(item.get("ttl_days"))
        expires_at = _normalized_expires_at(item.get("expires_at"))
        if not owner and ttl_days is None and not expires_at:
            continue
        rules.append(
            CleanupMetadataRule(
                path=path,
                glob=glob,
                kind=_normalized_text(item.get("kind", "")).lower(),
                category=_normalized_text(item.get("category", "")).lower(),
                owner=owner,
                ttl_days=ttl_days,
                expires_at=expires_at,
            )
        )
    return tuple(rules)


def _section_rules(raw: object, *, default_cleanup_extra_kinds: tuple[str, ...] = ()) -> ArchitectureRules:
    if not isinstance(raw, dict):
        return ArchitectureRules(cleanup_extra_kinds=default_cleanup_extra_kinds)
    return ArchitectureRules(
        ignore_paths=_string_list(raw.get("ignore_paths", [])),
        ignore_globs=_string_list(raw.get("ignore_globs", [])),
        ignore_extensions=_extension_list(raw.get("ignore_extensions", [])),
        cleanup_extra_kinds=_string_list(raw.get("cleanup_extra_kinds", list(default_cleanup_extra_kinds))),
        cleanup_metadata_rules=_cleanup_metadata_rules(raw.get("cleanup_metadata", [])),
    )


def _merge_lists(shared: tuple[str, ...], specific: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in (*shared, *specific):
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return tuple(merged)


def _defaults_for_tool(tool_name: str) -> tuple[str, ...]:
    if tool_name == "archi":
        return ("doc", "config", "prompt", "script")
    return ()


def load_architecture_rules(project_root: str | Path, *, tool_name: str) -> ArchitectureRules:
    root = Path(project_root).resolve()
    path = root / RULES_FILE_NAME
    default_cleanup = _defaults_for_tool(tool_name)
    if not path.exists():
        return ArchitectureRules(cleanup_extra_kinds=default_cleanup)
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ArchitectureRules(cleanup_extra_kinds=default_cleanup)
    if not isinstance(raw, dict):
        return ArchitectureRules(cleanup_extra_kinds=default_cleanup)
    shared = _section_rules(raw.get("shared", {}))
    specific = _section_rules(raw.get(tool_name, {}), default_cleanup_extra_kinds=default_cleanup)
    return ArchitectureRules(
        ignore_paths=_merge_lists(shared.ignore_paths, specific.ignore_paths),
        ignore_globs=_merge_lists(shared.ignore_globs, specific.ignore_globs),
        ignore_extensions=_merge_lists(shared.ignore_extensions, specific.ignore_extensions),
        cleanup_extra_kinds=_merge_lists(shared.cleanup_extra_kinds, specific.cleanup_extra_kinds),
        cleanup_metadata_rules=(*shared.cleanup_metadata_rules, *specific.cleanup_metadata_rules),
    )


def load_archi_rules(project_root: str | Path) -> ArchitectureRules:
    return load_architecture_rules(project_root, tool_name="archi")


def path_is_ignored(path: str | Path, rules: ArchitectureRules | None) -> bool:
    if rules is None:
        return False
    normalized = normalize_relpath(str(path or ""))
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = normalized.rstrip("/")
    if not normalized:
        return False
    suffix = Path(normalized).suffix.lower()
    if suffix and suffix in set(rules.ignore_extensions):
        return True
    for candidate in rules.ignore_paths:
        if normalized == candidate or normalized.startswith(f"{candidate}/"):
            return True
    rel_posix = PurePosixPath(normalized)
    for pattern in rules.ignore_globs:
        if fnmatchcase(normalized, pattern) or rel_posix.match(pattern):
            return True
    return False


def _matches_cleanup_metadata_rule(
    rule: CleanupMetadataRule,
    *,
    path: str,
    kind: str,
    category: str,
) -> bool:
    normalized_path = _normalized_relpath_text(path)
    normalized_kind = _normalized_text(kind).lower()
    normalized_category = _normalized_text(category).lower()
    if not normalized_path:
        return False
    if rule.kind and rule.kind != normalized_kind:
        return False
    if rule.category and rule.category != normalized_category:
        return False
    if rule.path and not (
        normalized_path == rule.path or normalized_path.startswith(f"{rule.path}/")
    ):
        return False
    if rule.glob:
        rel_posix = PurePosixPath(normalized_path)
        if not (fnmatchcase(normalized_path, rule.glob) or rel_posix.match(rule.glob)):
            return False
    return True


def _expires_at_is_expired(value: str) -> bool:
    text = _normalized_text(value)
    if not text:
        return False
    probe = text
    if probe.endswith("Z"):
        probe = probe[:-1] + "+00:00"
    try:
        parsed_dt = datetime.fromisoformat(probe)
    except ValueError:
        parsed_dt = None
    if parsed_dt is not None:
        if parsed_dt.tzinfo is None:
            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
        return parsed_dt < datetime.now(timezone.utc)
    try:
        parsed_date = date.fromisoformat(probe)
    except ValueError:
        return False
    return parsed_date < datetime.now(timezone.utc).date()


def cleanup_metadata_for_candidate(
    path: str | Path,
    *,
    rules: ArchitectureRules | None,
    kind: str = "",
    category: str = "",
) -> dict[str, Any]:
    if rules is None:
        return {}
    normalized_path = _normalized_relpath_text(path)
    if not normalized_path:
        return {}
    metadata: dict[str, Any] = {}
    for rule in rules.cleanup_metadata_rules:
        if not _matches_cleanup_metadata_rule(
            rule,
            path=normalized_path,
            kind=kind,
            category=category,
        ):
            continue
        if rule.owner:
            metadata["owner"] = rule.owner
        if rule.ttl_days is not None:
            metadata["ttl_days"] = rule.ttl_days
        if rule.expires_at:
            metadata["expires_at"] = rule.expires_at
            metadata["expired"] = _expires_at_is_expired(rule.expires_at)
    return metadata


__all__ = [
    "ArchitectureRules",
    "CleanupMetadataRule",
    "RULES_FILE_NAME",
    "cleanup_metadata_for_candidate",
    "load_architecture_rules",
    "load_archi_rules",
    "path_is_ignored",
]
