from __future__ import annotations

import os
from pathlib import Path


ARCHITECT_LLM_CONFIG_NAME = "architec-llm.yaml"


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


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
