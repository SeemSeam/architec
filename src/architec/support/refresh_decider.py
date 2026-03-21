from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from architec.integration.paths import REFRESH_STATE_PATH
from architec.integration.resource_paths import package_root
from architec.support.io_utils import read_json, write_json
from architec.support.refresh_decider_git import (
    _env_int,
    collect_git_change_signals,
)


_REFRESH_STATE_PATH = REFRESH_STATE_PATH
_REFRESH_STATE_VERSION = 1
_REFRESH_CONTRACT_FILES = (
    "config/rubric.json",
    "config/scoring-policy.json",
    "tools/collect_repo_metrics.py",
    "tools/build_architect_prompt.py",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_git_change_signals(root: Path) -> dict[str, Any]:
    return collect_git_change_signals(root)


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


def _disabled_refresh_result(mode: str, phase: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "phase": phase,
        "hippo_refresh": False,
        "metrics_refresh": False,
        "force_full_refresh": False,
        "reasons": ["refresh disabled by mode=never"],
        "signals": {},
    }


def _base_signals(*, hippo_needed: bool, metrics_needed: bool, fingerprint: str) -> dict[str, Any]:
    return {
        "hippo_needed": bool(hippo_needed),
        "metrics_needed": bool(metrics_needed),
        "refresh_contract_fingerprint": fingerprint,
    }


def _auto_refresh_decision(
    root: Path,
    *,
    state: dict[str, Any],
    fingerprint: str,
    baseline_phase: bool,
) -> tuple[bool, list[str], dict[str, Any]]:
    force_full = False
    reasons: list[str] = []
    signals: dict[str, Any] = {}
    if not baseline_phase:
        return force_full, reasons, signals

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
    return force_full, reasons, signals


def _refresh_flags(
    *,
    hippo_needed: bool,
    metrics_needed: bool,
    force_full: bool,
) -> tuple[bool, bool]:
    if force_full:
        return True, True
    return bool(hippo_needed), bool(metrics_needed)


def _append_default_reason(reasons: list[str], *, hippo_refresh: bool, metrics_refresh: bool) -> None:
    if reasons:
        return
    if hippo_refresh or metrics_refresh:
        reasons.append("source/context changed")
    else:
        reasons.append("no refresh needed")


def _persist_baseline_state(
    root: Path,
    *,
    state: dict[str, Any],
    mode: str,
    phase: str,
    baseline_phase: bool,
    force_full: bool,
    fingerprint: str,
    reasons: list[str],
) -> None:
    if not baseline_phase:
        return
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


def decide_refresh_actions(
    root: Path,
    *,
    refresh_mode: str,
    phase: str,
    hippo_needed: bool,
    metrics_needed: bool,
) -> dict[str, Any]:
    mode = str(refresh_mode or "auto").strip().lower() or "auto"
    state = _load_state(root)

    if mode == "never":
        return _disabled_refresh_result(mode, phase)

    reasons: list[str] = []
    force_full = False
    if mode == "always":
        force_full = True
        reasons.append("refresh forced by mode=always")

    baseline_phase = str(phase or "").strip().lower() == "baseline"
    fingerprint = _refresh_contract_fingerprint(root)
    signals = _base_signals(
        hippo_needed=hippo_needed,
        metrics_needed=metrics_needed,
        fingerprint=fingerprint,
    )

    if mode == "auto":
        auto_force_full, auto_reasons, auto_signals = _auto_refresh_decision(
            root,
            state=state,
            fingerprint=fingerprint,
            baseline_phase=baseline_phase,
        )
        force_full = force_full or auto_force_full
        reasons.extend(auto_reasons)
        signals.update(auto_signals)

    hippo_refresh, metrics_refresh = _refresh_flags(
        hippo_needed=hippo_needed,
        metrics_needed=metrics_needed,
        force_full=force_full,
    )
    _append_default_reason(
        reasons,
        hippo_refresh=hippo_refresh,
        metrics_refresh=metrics_refresh,
    )
    _persist_baseline_state(
        root,
        state=state,
        mode=mode,
        phase=phase,
        baseline_phase=baseline_phase,
        force_full=force_full,
        fingerprint=fingerprint,
        reasons=reasons,
    )

    return {
        "mode": mode,
        "phase": phase,
        "hippo_refresh": hippo_refresh,
        "metrics_refresh": metrics_refresh,
        "force_full_refresh": force_full,
        "reasons": reasons,
        "signals": signals,
    }
