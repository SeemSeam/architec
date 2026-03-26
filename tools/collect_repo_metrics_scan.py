from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_EXCLUDE_DIRS = {
    ".architec",
    ".hippocampus",
    ".git",
    "__pycache__",
}


def iter_files(root: Path, exclude_dirs: set[str], exclude_suffixes: set[str]) -> list[Path]:
    effective_exclude_dirs = set(exclude_dirs) | DEFAULT_EXCLUDE_DIRS
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in effective_exclude_dirs for part in rel.parts):
            continue
        if path.suffix.lower() in exclude_suffixes:
            continue
        out.append(path)
    return out


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def is_probably_binary(path: Path, sample_size: int = 2048) -> bool:
    try:
        chunk = path.read_bytes()[:sample_size]
    except Exception:
        return False
    if not chunk:
        return False
    if b"\x00" in chunk:
        return True
    printable = sum(1 for byte in chunk if 32 <= byte <= 126 or byte in (9, 10, 13))
    return (printable / len(chunk)) < 0.7


def module_size_findings(*, rel: str, line_count: int, thr) -> list[dict[str, Any]]:
    if line_count > thr.module_hard:
        return [
            {
                "id": "module_lines_hard",
                "dimension": "file_size",
                "severity": "critical",
                "path": rel,
                "metric": "module_lines",
                "value": line_count,
                "threshold": thr.module_hard,
                "message": "File exceeds hard module size threshold.",
            }
        ]
    if line_count > thr.module_soft:
        return [
            {
                "id": "module_lines_soft",
                "dimension": "file_size",
                "severity": "warning",
                "path": rel,
                "metric": "module_lines",
                "value": line_count,
                "threshold": thr.module_soft,
                "message": "File exceeds soft module size threshold.",
            }
        ]
    return []


def line_length_summary(*, rel: str, lines: list[str], thr) -> dict[str, Any]:
    longest = 0
    soft_hits = 0
    hard_hits = 0
    hard_samples: list[int] = []
    for idx, line in enumerate(lines, start=1):
        line_len = len(line)
        longest = max(longest, line_len)
        if line_len > thr.line_soft:
            soft_hits += 1
        if line_len > thr.line_hard:
            hard_hits += 1
            if len(hard_samples) < 5:
                hard_samples.append(idx)

    findings: list[dict[str, Any]] = []
    if hard_hits > 0:
        findings.append(
            {
                "id": "line_length_hard",
                "dimension": "code_style",
                "severity": "warning",
                "path": rel,
                "metric": "line_length_hard_hits",
                "value": hard_hits,
                "threshold": thr.line_hard,
                "longest_line": longest,
                "sample_lines": hard_samples,
                "message": "File contains lines above hard line length threshold.",
            }
        )
    elif soft_hits > 0:
        findings.append(
            {
                "id": "line_length_soft",
                "dimension": "code_style",
                "severity": "info",
                "path": rel,
                "metric": "line_length_soft_hits",
                "value": soft_hits,
                "threshold": thr.line_soft,
                "message": "File contains long lines above soft threshold.",
            }
        )

    return {
        "findings": findings,
        "soft_hits": soft_hits,
        "hard_hits": hard_hits,
        "longest": longest,
    }
