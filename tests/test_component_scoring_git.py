from __future__ import annotations

import subprocess

import pytest

from architec.scoring import component_scoring_git


def test_changed_files_raises_for_explicit_bad_git_range(tmp_path, monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=128,
            stdout="",
            stderr="fatal: bad revision 'missing...HEAD'\n",
        )

    monkeypatch.setattr(component_scoring_git.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="git range error"):
        component_scoring_git.changed_files(tmp_path, base="missing", head="HEAD")


def test_changed_files_returns_empty_for_valid_empty_explicit_range(tmp_path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(component_scoring_git.subprocess, "run", fake_run)

    assert component_scoring_git.changed_files(tmp_path, base="main", head="HEAD") == []
    assert calls == [["git", "diff", "--numstat", "main...HEAD"]]
