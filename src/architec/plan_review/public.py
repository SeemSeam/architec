from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_YAML_FENCE_RE = re.compile(
    r"^```[ \t]*(?:yaml|yml)?[ \t]*\n(.*?)^```",
    re.MULTILINE | re.DOTALL,
)


def _heading_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _markdown_sections(markdown: str) -> dict[str, str]:
    lines = markdown.splitlines()
    headings: list[tuple[int, str, int]] = []
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        headings.append((len(match.group(1)), _heading_key(match.group(2)), index))

    sections: dict[str, str] = {}
    for heading_index, (level, key, start_line) in enumerate(headings):
        end_line = len(lines)
        for next_level, _next_key, next_line in headings[heading_index + 1 :]:
            if next_level <= level:
                end_line = next_line
                break
        sections.setdefault(key, "\n".join(lines[start_line + 1 : end_line]).strip())
    return sections


def _section_text(sections: dict[str, str], title: str) -> str:
    return str(sections.get(_heading_key(title), "") or "").strip()


def _extract_intent(sections: dict[str, str]) -> str:
    intent = _section_text(sections, "Intent")
    if intent:
        return intent.strip()
    return ""


def _load_yaml_object(raw: str) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _extract_yaml_plan(changes_section: str, markdown: str) -> dict[str, Any]:
    for source in (changes_section, markdown):
        for match in _YAML_FENCE_RE.finditer(source):
            loaded = _load_yaml_object(match.group(1))
            if "changes" in loaded or "dependencies" in loaded:
                return loaded

    loaded = _load_yaml_object(changes_section)
    if "changes" in loaded or "dependencies" in loaded:
        return loaded
    return {}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def _normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return [_json_safe(value)]


def _plan_fingerprint(understood_plan: dict[str, Any]) -> str:
    encoded = json.dumps(
        understood_plan,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _missing_changes_concern(plan_path: Path) -> dict[str, Any]:
    return {
        "concern_id": "plan-review:missing-context:changes",
        "kind": "missing-context",
        "level": "caution",
        "confidence": 1.0,
        "location": {
            "path": str(plan_path),
            "line": 0,
            "symbol": "",
            "symbol_kind": "module",
        },
        "root_cause": "No structured changes entries were recognized from the Markdown plan.",
        "evidence": [
            "The understood plan has an empty changes list.",
            "No YAML changes entries were parsed from the Changes section.",
        ],
        "blast_radius": [],
        "next_steps_hint": "Add changes entries with action, path, and intent.",
    }


def run_plan_review(
    plan_path: str | Path,
    *,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(plan_path).resolve()
    root = Path(project_root).resolve() if project_root is not None else Path.cwd().resolve()
    markdown = path.read_text(encoding="utf-8")
    sections = _markdown_sections(markdown)
    yaml_plan = _extract_yaml_plan(_section_text(sections, "Changes"), markdown)
    understood_plan = {
        "intent": _extract_intent(sections),
        "changes": _normalize_list(yaml_plan.get("changes")),
        "dependencies": _normalize_list(yaml_plan.get("dependencies")),
    }
    concerns = []
    if not understood_plan["changes"]:
        concerns.append(_missing_changes_concern(path))

    return {
        "mode": "plan_review",
        "understood_plan": understood_plan,
        "concerns": concerns,
        "suggested_adjustments": [],
        "plan_fingerprint": _plan_fingerprint(understood_plan),
        "artifacts": {
            "plan_path": str(path),
            "project_root": str(root),
            "parser": "markdown_yaml_v1",
        },
    }


__all__ = [
    "run_plan_review",
]
