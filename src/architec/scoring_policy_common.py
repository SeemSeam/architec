from __future__ import annotations

from pathlib import Path
from typing import Any

from .io_utils import read_json
from .resource_paths import resolve_config_file
from .scoring_policy_defaults import DEFAULT_POLICY


def to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in base.items():
        if isinstance(value, dict):
            override_value = (
                override.get(key, {})
                if isinstance(override.get(key, {}), dict)
                else {}
            )
            out[key] = merge_dict(value, override_value)
            continue
        out[key] = override.get(key, value)
    for key, value in override.items():
        if key not in out:
            out[key] = value
    return out


def load_scoring_policy(project_root: str | Path) -> dict[str, Any]:
    policy_path = resolve_config_file(project_root, "scoring-policy.json")
    loaded = read_json(policy_path, default={})
    if not isinstance(loaded, dict):
        loaded = {}
    return merge_dict(DEFAULT_POLICY, loaded)


def grade_for_score(score: float, policy: dict[str, Any]) -> str:
    raw = policy.get("grade_bands", [])
    bands: list[dict[str, Any]] = [x for x in raw if isinstance(x, dict)]
    if not bands:
        bands = DEFAULT_POLICY["grade_bands"]  # type: ignore[assignment]
    bands = sorted(bands, key=lambda x: to_float(x.get("min"), 0.0), reverse=True)
    for band in bands:
        if score >= to_float(band.get("min"), 0.0):
            return str(band.get("grade", "") or "E")
    return "E"


def recommend(score: float, *, pass_min: float, warn_min: float) -> str:
    if score >= pass_min:
        return "approve"
    if score >= warn_min:
        return "needs_changes"
    return "block"
