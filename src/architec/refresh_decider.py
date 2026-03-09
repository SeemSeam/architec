from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io_utils import read_json, write_json
from .paths import REFRESH_STATE_PATH
from .resource_paths import package_root


_REFRESH_STATE_PATH = REFRESH_STATE_PATH
_REFRESH_STATE_VERSION = 1
_REFRESH_CONTRACT_FILES = (
    "config/rubric.json",
    "config/scoring-policy.json",
    "tools/collect_repo_metrics.py",
    "tools/build_architect_prompt.py",
)
_RELEVANT_PREFIXES = (
    "hippocampus/",
    "llm-proxy/",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _collect_git_change_signals(root: Path) -> dict[str, Any]:
    rows = []
    for raw in _run_git_status(root).splitlines():
        if len(raw) < 4:
            continue
        code = raw[:2]
        path = _normalize_status_path(raw[3:])
        if not path or not _is_relevant_path(path):
            continue
        structural = (
            "R" in code
            or "D" in code
            or "C" in code
            or " -> " in raw
        )
        rows.append({"code": code, "path": path, "structural": structural})

    changed_total = len(rows)
    structural_total = sum(1 for item in rows if bool(item.get("structural", False)))
    ratio = (float(structural_total) / float(changed_total)) if changed_total > 0 else 0.0

    min_structural = max(1, _env_int("ARCH_FULL_REFRESH_STRUCTURAL_MIN", 8))
    min_changed = max(1, _env_int("ARCH_FULL_REFRESH_CHANGED_MIN", 30))
    min_ratio = max(0.0, min(1.0, _env_float("ARCH_FULL_REFRESH_STRUCTURAL_RATIO", 0.35)))

    trigger = bool(structural_total >= min_structural) or bool(
        changed_total >= min_changed and ratio >= min_ratio
    )
    return {
        "changed_total": changed_total,
        "structural_total": structural_total,
        "structural_ratio": round(ratio, 4),
        "trigger": trigger,
        "thresholds": {
            "min_structural": min_structural,
            "min_changed": min_changed,
            "min_ratio": min_ratio,
        },
    }


def _refresh_contract_fingerprint(root: Path) -> str:
    parts: list[str] = []
    base = package_root()
    for rel in _REFRESH_CONTRACT_FILES:
        path = base / rel
        if not path.exists() or not path.is_file():
            parts.append(f"{rel}:missing")
            continue
        try:
            stat = path.stat()
            parts.append(f"{rel}:{int(stat.st_mtime_ns)}:{int(stat.st_size)}")
        except OSError:
            parts.append(f"{rel}:error")
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _state_path(root: Path) -> Path:
    return root / _REFRESH_STATE_PATH


def _load_state(root: Path) -> dict[str, Any]:
    data = read_json(_state_path(root), default={})
    if not isinstance(data, dict):
        return {}
    return data


def _save_state(root: Path, state: dict[str, Any]) -> None:
    write_json(_state_path(root), state)


def decide_refresh_actions(
    root: Path,
    *,
    refresh_mode: str,
    phase: str,
    hippo_needed: bool,
    metrics_needed: bool,
) -> dict[str, Any]:
    mode = str(refresh_mode or "auto").strip().lower() or "auto"
    reasons: list[str] = []
    force_full = False
    state = _load_state(root)

    if mode == "never":
        out = {
            "mode": mode,
            "phase": phase,
            "hippo_refresh": False,
            "metrics_refresh": False,
            "force_full_refresh": False,
            "reasons": ["refresh disabled by mode=never"],
            "signals": {},
        }
        return out

    if mode == "always":
        force_full = True
        reasons.append("refresh forced by mode=always")

    baseline_phase = str(phase or "").strip().lower() == "baseline"
    fingerprint = _refresh_contract_fingerprint(root)

    signals: dict[str, Any] = {
        "hippo_needed": bool(hippo_needed),
        "metrics_needed": bool(metrics_needed),
        "refresh_contract_fingerprint": fingerprint,
    }

    if mode == "auto" and baseline_phase:
        previous_fingerprint = str(state.get("refresh_contract_fingerprint", "") or "")
        if previous_fingerprint and previous_fingerprint != fingerprint:
            force_full = True
            reasons.append("refresh-contract changed")

        structural = _collect_git_change_signals(root)
        signals["git_changes"] = structural
        if bool(structural.get("trigger", False)):
            force_full = True
            reasons.append("large structural change detected")

        interval = max(1, _env_int("ARCH_FULL_REFRESH_INTERVAL", 5))
        runs_since_full = int(state.get("baseline_runs_since_full", 0) or 0)
        signals["periodic"] = {
            "interval": interval,
            "runs_since_full": runs_since_full,
        }
        if (runs_since_full + 1) >= interval:
            force_full = True
            reasons.append("periodic full refresh")

    hippo_refresh = bool(hippo_needed)
    metrics_refresh = bool(metrics_needed)
    if force_full:
        hippo_refresh = True
        metrics_refresh = True

    if not reasons:
        if hippo_refresh or metrics_refresh:
            reasons.append("source/context changed")
        else:
            reasons.append("no refresh needed")

    if baseline_phase:
        runs_since_full = int(state.get("baseline_runs_since_full", 0) or 0)
        next_runs = 0 if force_full else (runs_since_full + 1)
        new_state = {
            "version": _REFRESH_STATE_VERSION,
            "updated_at": _utc_now_iso(),
            "baseline_runs_since_full": int(next_runs),
            "refresh_contract_fingerprint": fingerprint,
            "last_mode": mode,
            "last_phase": phase,
            "last_reasons": reasons[:6],
        }
        if force_full:
            new_state["last_full_refresh_at"] = _utc_now_iso()
            new_state["last_full_refresh_reasons"] = reasons[:6]
        _save_state(root, new_state)

    return {
        "mode": mode,
        "phase": phase,
        "hippo_refresh": hippo_refresh,
        "metrics_refresh": metrics_refresh,
        "force_full_refresh": force_full,
        "reasons": reasons,
        "signals": signals,
    }
