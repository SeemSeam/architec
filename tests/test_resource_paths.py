from __future__ import annotations

from pathlib import Path

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
