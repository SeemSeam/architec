from __future__ import annotations

import sys
from pathlib import Path

import pytest

from architec import self_manage


def test_handle_self_manage_command_returns_none_for_normal_args() -> None:
    assert self_manage.handle_self_manage_command(["--check", "."]) is None


def test_update_reinstalls_even_when_current_matches_latest(monkeypatch, capsys) -> None:
    monkeypatch.setattr(self_manage, "current_cli_version", lambda: "0.2.1")
    monkeypatch.setattr(self_manage, "_latest_release_version", lambda _url: "0.2.1")
    calls: list[str] = []
    monkeypatch.setattr(self_manage, "_run_install_script", lambda url: calls.append(url) or 0)

    result = self_manage.handle_self_manage_command(["update"])

    assert result == 0
    assert calls == [self_manage.DEFAULT_INSTALL_SCRIPT_URL]
    out = capsys.readouterr().out
    assert "Current version: 0.2.1" in out
    assert "Latest version: 0.2.1" in out
    assert "reinstalling 0.2.1" in out


def test_update_runs_installer_when_latest_is_newer(monkeypatch, capsys) -> None:
    monkeypatch.setattr(self_manage, "current_cli_version", lambda: "0.2.0")
    monkeypatch.setattr(self_manage, "_latest_release_version", lambda _url: "0.2.1")
    calls: list[str] = []
    monkeypatch.setattr(self_manage, "_run_install_script", lambda url: calls.append(url) or 0)

    result = self_manage.handle_self_manage_command(["update", "--install-script-url", "https://example.com/install.sh"])

    assert result == 0
    assert calls == ["https://example.com/install.sh"]
    out = capsys.readouterr().out
    assert "Current version: 0.2.0" in out
    assert "Latest version: 0.2.1" in out


def test_print_version_status_reports_update_available(monkeypatch, capsys) -> None:
    monkeypatch.setattr(self_manage, "current_cli_version", lambda: "0.2.1")
    monkeypatch.setattr(self_manage, "_latest_release_version", lambda _url: "0.2.2")

    result = self_manage.print_version_status()

    assert result == 0
    out = capsys.readouterr().out
    assert "Architec CLI version: 0.2.1" in out
    assert "Latest release: 0.2.2" in out
    assert "Update available: yes" in out
    assert "Run: archi update" in out


def test_print_version_status_handles_release_lookup_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(self_manage, "current_cli_version", lambda: "0.2.1")
    monkeypatch.setattr(
        self_manage,
        "_latest_release_version",
        lambda _url: (_ for _ in ()).throw(RuntimeError("network down")),
    )

    result = self_manage.print_version_status()

    assert result == 0
    out = capsys.readouterr().out
    assert "Architec CLI version: 0.2.1" in out
    assert "Latest release: unknown" in out
    assert "Latest check failed: network down" in out


def test_uninstall_removes_install_and_managed_skills(tmp_path: Path, monkeypatch, capsys) -> None:
    home = tmp_path / "home"
    install_base = home / ".local" / "architec"
    bin_dir = home / ".local" / "bin"
    archi_bin = bin_dir / "archi"
    repomix_bin = bin_dir / "repomix"
    repomix_target = install_base / "node-tools" / "repomix" / "node_modules" / ".bin" / "repomix"
    codex_skills = home / ".codex" / "skills"
    claude_skills = home / ".claude" / "skills"

    repomix_target.parent.mkdir(parents=True, exist_ok=True)
    install_base.mkdir(parents=True, exist_ok=True)
    bin_dir.mkdir(parents=True, exist_ok=True)
    archi_bin.write_text("", encoding="utf-8")
    repomix_target.write_text("", encoding="utf-8")
    repomix_bin.symlink_to(repomix_target)
    for root in (codex_skills, claude_skills):
        for name in self_manage.MANAGED_SKILL_NAMES:
            (root / name).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(self_manage, "_uninstall_python_deps", lambda: 0)

    result = self_manage.handle_self_manage_command(["uninstall", "--yes"])

    assert result == 0
    assert not install_base.exists()
    assert not archi_bin.exists()
    assert not repomix_bin.exists()
    for root in (codex_skills, claude_skills):
        for name in self_manage.MANAGED_SKILL_NAMES:
            assert not (root / name).exists()
    out = capsys.readouterr().out
    assert "Config purge: enabled" in out
    assert "Python dependency removal attempted" in out
    assert "Architec uninstall complete." in out


def test_uninstall_removes_config_and_deps_by_default(monkeypatch, tmp_path: Path, capsys) -> None:
    home = tmp_path / "home"
    (home / ".architec").mkdir(parents=True)
    (home / ".hippocampus").mkdir(parents=True)
    (home / ".llmgateway").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(self_manage, "_uninstall_python_deps", lambda: 0)

    result = self_manage.handle_self_manage_command(["uninstall", "--yes"])

    assert result == 0
    assert not (home / ".architec").exists()
    assert not (home / ".hippocampus").exists()
    assert not (home / ".llmgateway").exists()
    out = capsys.readouterr().out
    assert "Config purge: enabled" in out
    assert "Python dependency removal attempted" in out


def test_cli_main_dispatches_self_manage_before_auth(monkeypatch) -> None:
    import architec.cli as cli

    monkeypatch.setattr(sys, "argv", ["archi", "update"])
    monkeypatch.setattr(cli, "handle_self_manage_command", lambda argv: 0)
    monkeypatch.setattr(cli, "handle_auth_command", lambda argv: pytest.fail("auth dispatch should not run"))

    assert cli.main() == 0
