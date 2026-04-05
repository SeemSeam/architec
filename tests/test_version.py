from __future__ import annotations

from pathlib import Path

from architec import _version
from architec import version


def test_current_cli_version_prefers_packaged_version_when_metadata_is_stale(monkeypatch, tmp_path):
    fake_module_path = tmp_path / "bundle" / "architec" / "version.py"
    fake_module_path.parent.mkdir(parents=True)
    fake_module_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(version, "__file__", str(fake_module_path))
    monkeypatch.setattr(version, "PACKAGE_VERSION", "0.2.7")
    monkeypatch.setattr(version.metadata, "version", lambda _: "0.2.4")

    assert version.current_cli_version() == "0.2.7"


def test_packaged_version_matches_project_metadata():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    payload = version.tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert _version.__version__ == payload["project"]["version"]
