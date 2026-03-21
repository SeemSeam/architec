from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


_RELEVANT_PREFIXES = (
    "hippocampus/",
    "llm-proxy/",
)


def _env_int(name: str, default: int) -> int:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _env_float(name: str, default: float) -> float:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _run_git_status(root: Path) -> str:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return str(proc.stdout or "")


def _normalize_status_path(raw: str) -> str:
    text = str(raw or "").strip()
    if " -> " in text:
        text = text.split(" -> ", 1)[1]
    return text.replace("\\", "/")


def _is_relevant_path(path: str) -> bool:
    p = str(path or "")
    return any(p.startswith(prefix) for prefix in _RELEVANT_PREFIXES)


def _status_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for raw in _run_git_status(root).splitlines():
        if len(raw) < 4:
            continue
        code = raw[:2]
        path = _normalize_status_path(raw[3:])
        if not path or not _is_relevant_path(path):
            continue
        rows.append(
            {
                "code": code,
                "path": path,
                "structural": ("R" in code or "D" in code or "C" in code or " -> " in raw),
            }
        )
    return rows


def _git_change_thresholds() -> dict[str, float]:
    return {
        "min_structural": max(1, _env_int("ARCH_FULL_REFRESH_STRUCTURAL_MIN", 8)),
        "min_changed": max(1, _env_int("ARCH_FULL_REFRESH_CHANGED_MIN", 30)),
        "min_ratio": max(0.0, min(1.0, _env_float("ARCH_FULL_REFRESH_STRUCTURAL_RATIO", 0.35))),
    }


def _git_change_summary(rows: list[dict[str, Any]], thresholds: dict[str, float]) -> dict[str, Any]:
    changed_total = len(rows)
    structural_total = sum(1 for item in rows if bool(item.get("structural", False)))
    ratio = (float(structural_total) / float(changed_total)) if changed_total > 0 else 0.0
    trigger = bool(structural_total >= thresholds["min_structural"]) or bool(
        changed_total >= thresholds["min_changed"] and ratio >= thresholds["min_ratio"]
    )
    return {
        "changed_total": changed_total,
        "structural_total": structural_total,
        "structural_ratio": round(ratio, 4),
        "trigger": trigger,
        "thresholds": thresholds,
    }


def collect_git_change_signals(root: Path) -> dict[str, Any]:
    return _git_change_summary(_status_rows(root), _git_change_thresholds())
