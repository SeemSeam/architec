from __future__ import annotations

import os
import site
import sys
import sysconfig
from pathlib import Path


ARCHITECT_LLM_CONFIG_NAME = "config.yaml"


def _has_packaged_resources(candidate: Path) -> bool:
    return (candidate / "config").exists() or (candidate / "prompts").exists()


def package_root() -> Path:
    override = str(os.environ.get("ARCHITEC_PACKAGE_ROOT", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    executable_candidates = []
    for raw in (sys.argv[0], sys.executable):
        if not raw:
            continue
        candidate = Path(raw).expanduser().resolve().parent
        if candidate not in executable_candidates:
            executable_candidates.append(candidate)
    for candidate in executable_candidates:
        if _has_packaged_resources(candidate):
            return candidate

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent

    install_roots = []
    for raw in (
        sysconfig.get_path("data"),
        sys.prefix,
        getattr(sys, "base_prefix", ""),
        site.getuserbase(),
    ):
        if not raw:
            continue
        candidate = Path(raw).expanduser().resolve() / "architec"
        if candidate not in install_roots:
            install_roots.append(candidate)
    for candidate in install_roots:
        if _has_packaged_resources(candidate):
            return candidate

    return current.parents[3]


def package_config_dir() -> Path:
    override = str(os.environ.get("ARCHITEC_CONFIG_DIR", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return package_root() / "config"


def package_prompts_dir() -> Path:
    override = str(os.environ.get("ARCHITEC_PROMPTS_DIR", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return package_root() / "prompts"


def package_tools_dir() -> Path:
    return package_root() / "tools"


def user_config_dir() -> Path:
    override = str(os.environ.get("ARCHITEC_USER_CONFIG_DIR", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".architec").resolve()


def project_state_dir(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / ".architec"


def resolve_project_or_package_file(
    project_root: str | Path,
    *,
    override_name: str,
    package_dir: Path,
) -> Path:
    root = Path(project_root).resolve()
    local_override = root / ".architec" / override_name
    if local_override.exists():
        return local_override
    user_override = user_config_dir() / override_name
    if user_override.exists():
        return user_override
    return package_dir / override_name


def resolve_config_file(project_root: str | Path, name: str) -> Path:
    return resolve_project_or_package_file(
        project_root,
        override_name=name,
        package_dir=package_config_dir(),
    )


def resolve_architect_llm_config_file(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    local_override = root / ".architec" / ARCHITECT_LLM_CONFIG_NAME
    if local_override.exists():
        return local_override
    return user_config_dir() / ARCHITECT_LLM_CONFIG_NAME


def resolve_prompt_file(project_root: str | Path | None, name: str) -> Path | None:
    if project_root is not None:
        root = Path(project_root).resolve()
        legacy = root / "architec" / "prompts" / name
        if legacy.exists():
            return legacy
    prompt_path = package_prompts_dir() / name
    if prompt_path.exists():
        return prompt_path
    return None


def tool_script_path(name: str) -> Path:
    return package_tools_dir() / name
