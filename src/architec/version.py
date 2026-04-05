from __future__ import annotations

import os
from importlib import metadata
from pathlib import Path

from ._version import __version__ as PACKAGE_VERSION

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib


def _version_from_source_tree() -> str:
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
    return ""


def current_cli_version() -> str:
    override = str(os.environ.get("ARCHITEC_CLI_VERSION_OVERRIDE", "") or "").strip()
    if override:
        return override
    source_tree_version = _version_from_source_tree()
    if source_tree_version:
        return source_tree_version
    packaged_version = str(PACKAGE_VERSION or "").strip()
    if packaged_version:
        return packaged_version
    try:
        return metadata.version("architec")
    except metadata.PackageNotFoundError:
        pass
    return "0.0.0"
