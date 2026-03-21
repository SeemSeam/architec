from __future__ import annotations

import os
from importlib import metadata
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


def current_cli_version() -> str:
    override = str(os.environ.get("ARCHITEC_CLI_VERSION_OVERRIDE", "") or "").strip()
    if override:
        return override
    try:
        return metadata.version("architec")
    except metadata.PackageNotFoundError:
        pass
    for parent in Path(__file__).resolve().parents:
        pyproject = parent / "pyproject.toml"
        if not pyproject.exists():
            continue
        try:
            payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            version = str(payload["project"]["version"]).strip()
        except Exception:
            continue
        if version:
            return version
    return "0.0.0"
