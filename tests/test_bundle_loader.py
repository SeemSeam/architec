from __future__ import annotations

from pathlib import Path

from architec.bundle_loader import inspect_bundle, require_bundle


def _touch(path: Path, content: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_inspect_bundle_reports_missing_files(tmp_path):
    status = inspect_bundle(tmp_path)
    assert status.ok is False
    assert ".hippocampus/architect-metrics.json" in status.missing_files


def test_require_bundle_passes_when_all_required_files_exist(tmp_path):
    _touch(tmp_path / ".hippocampus" / "architect-metrics.json")
    _touch(tmp_path / ".hippocampus" / "hippocampus-index.json")
    _touch(tmp_path / ".hippocampus" / "code-signatures.json")
    _touch(tmp_path / ".hippocampus" / "structure-prompt.md", "# prompt\n")

    status = require_bundle(tmp_path)
    assert status.ok is True
