from __future__ import annotations

from pathlib import Path

import architec.integration.hippo_bridge as hippo_bridge


def _touch(path: Path, content: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_refresh_bundle_from_hippo_runs_expected_steps(tmp_path, monkeypatch):
    executed: list[list[str]] = []

    def fake_run(cmd, *, cwd):
        executed.append(list(cmd))
        joined = " ".join(cmd)
        if "collect_repo_metrics.py" in joined:
            _touch(tmp_path / ".hippocampus" / "architect-metrics.json")
        elif "sig-extract" in cmd:
            _touch(tmp_path / ".hippocampus" / "code-signatures.json")
        elif "index" in cmd:
            _touch(tmp_path / ".hippocampus" / "hippocampus-index.json")
        elif "structure-prompt" in cmd:
            _touch(tmp_path / ".hippocampus" / "structure-prompt.md", "# prompt\n")
        return {"cmd": cmd, "returncode": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(hippo_bridge, "_hippo_base_command", lambda root: ["hippo"])
    monkeypatch.setattr(hippo_bridge, "_run", fake_run)

    result = hippo_bridge.refresh_bundle_from_hippo(tmp_path)

    assert result["ok"] is True
    assert len(executed) == 6
    assert executed[0] == ["hippo", "init", str(tmp_path)]
    assert executed[1] == ["hippo", "sig-extract", str(tmp_path)]
    assert executed[2] == ["hippo", "tree", str(tmp_path)]
    assert executed[3] == ["hippo", "index", "--no-llm", str(tmp_path)]
    assert executed[4] == [
        "hippo",
        "structure-prompt",
        "--profile",
        "map",
        "--no-llm-enhance",
        str(tmp_path),
    ]
    assert any("sig-extract" in cmd for cmd in executed)
    assert any("tree" in cmd for cmd in executed)
    assert any("index" in cmd for cmd in executed)
    assert any("structure-prompt" in cmd for cmd in executed)


def test_refresh_bundle_from_hippo_raises_on_failed_step(tmp_path, monkeypatch):
    monkeypatch.setattr(hippo_bridge, "_hippo_base_command", lambda root: ["hippo"])
    monkeypatch.setattr(
        hippo_bridge,
        "_run",
        lambda cmd, *, cwd: {
            "cmd": cmd,
            "returncode": 1 if "index" in cmd else 0,
            "stdout": "",
            "stderr": "boom" if "index" in cmd else "",
        },
    )

    try:
        hippo_bridge.refresh_bundle_from_hippo(tmp_path)
    except RuntimeError as exc:
        assert "refresh-from-hippo failed" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_hippo_base_command_uses_python_module_when_cli_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(hippo_bridge.shutil, "which", lambda name: None)

    class _Spec:
        pass

    monkeypatch.setattr(hippo_bridge.importlib.util, "find_spec", lambda name: _Spec() if name == "hippocampus.cli" else None)

    assert hippo_bridge._hippo_base_command(tmp_path) == [hippo_bridge.sys.executable, "-m", "hippocampus.cli"]
