from __future__ import annotations

from pathlib import Path

from architec.integration import resource_paths
from architec.integration.resource_paths import (
    resolve_architect_llm_config_file,
    resolve_config_file,
)


def test_resolve_config_file_prefers_project_override(tmp_path: Path) -> None:
    override = tmp_path / ".architec" / "scoring-policy.json"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text("{}", encoding="utf-8")

    resolved = resolve_config_file(tmp_path, "scoring-policy.json")
    assert resolved == override


def test_resolve_config_file_uses_user_config_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    user_dir = tmp_path / ".global-architec"
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(user_dir))
    override = user_dir / "scoring-policy.json"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text("{}", encoding="utf-8")

    resolved = resolve_config_file(tmp_path, "scoring-policy.json")
    assert resolved == override


def test_resolve_architect_llm_config_file_prefers_project_override(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(tmp_path / ".global-architec"))
    override = tmp_path / ".architec" / "config.yaml"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text("{}", encoding="utf-8")

    resolved = resolve_architect_llm_config_file(tmp_path)
    assert resolved == override


def test_resolve_architect_llm_config_file_uses_user_config_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    user_dir = tmp_path / ".global-architec"
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(user_dir))

    resolved = resolve_architect_llm_config_file(tmp_path)
    assert resolved == user_dir / "config.yaml"


def test_package_root_uses_installed_data_files_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module_path = (
        tmp_path
        / "venv"
        / "lib"
        / "python3.11"
        / "site-packages"
        / "architec"
        / "integration"
        / "resource_paths.py"
    )
    module_path.parent.mkdir(parents=True)
    module_path.write_text("", encoding="utf-8")

    installed_root = tmp_path / "venv" / "architec"
    (installed_root / "config").mkdir(parents=True)

    monkeypatch.setattr(resource_paths, "__file__", str(module_path))
    monkeypatch.setattr(
        resource_paths.sysconfig,
        "get_path",
        lambda name: str(tmp_path / "venv") if name == "data" else "",
    )
    monkeypatch.setattr(resource_paths.site, "getuserbase", lambda: str(tmp_path / "user"))

    assert resource_paths.package_root() == installed_root.resolve()
