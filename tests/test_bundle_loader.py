from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from architec.integration.bundle_loader import (
    compute_bundle_fingerprint,
    inspect_bundle,
    require_bundle,
)


def _touch(path: Path, content: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_valid_bundle(
    root: Path,
    *,
    metrics_payload: dict | None = None,
    with_bundle_state: bool = True,
    bundle_dir_name: str = ".hippocampus",
    index_name: str = "hippocampus-index.json",
) -> None:
    _touch(root / "src" / "app.py", "print('ok')\n")
    hippo = root / bundle_dir_name
    _touch(hippo / index_name, '{"files": {"src/app.py": {}}}\n')
    _touch(hippo / "code-signatures.json", '{"files": {"src/app.py": {"signatures": []}}}\n')
    _touch(hippo / "file-manifest.json", '{"files": {"src/app.py": {"kind": "source"}}}\n')
    _touch(hippo / "structure-prompt.md", "# prompt\n")
    fingerprint = compute_bundle_fingerprint(root)
    generated_at = datetime.now(timezone.utc).isoformat()
    if with_bundle_state:
        _touch(
            hippo / "bundle-state.json",
            json.dumps({"bundle_fingerprint": fingerprint, "generated_at": generated_at}) + "\n",
        )
    payload = {"bundle_fingerprint": fingerprint, "generated_at": generated_at}
    if metrics_payload:
        payload.update(metrics_payload)
    _touch(hippo / "architect-metrics.json", json.dumps(payload) + "\n")


def test_inspect_bundle_reports_missing_files(tmp_path):
    status = inspect_bundle(tmp_path)
    assert status.ok is False
    assert ".hippos/architect-metrics.json" in status.missing_files


def test_require_bundle_passes_when_all_required_files_exist(tmp_path):
    _write_valid_bundle(tmp_path)

    status = require_bundle(tmp_path)
    assert status.ok is True
    assert status.bundle_state_present is True
    assert status.bundle_state_fingerprint == status.metrics_fingerprint


def test_require_bundle_passes_with_canonical_hippos_bundle(tmp_path):
    _write_valid_bundle(
        tmp_path,
        bundle_dir_name=".hippos",
        index_name="hippos-index.json",
    )

    status = require_bundle(tmp_path)
    assert status.ok is True
    assert ".hippos/hippos-index.json" in status.present_files


def test_inspect_bundle_marks_metrics_without_fingerprint_as_stale(tmp_path):
    _touch(tmp_path / "src" / "app.py", "print('ok')\n")
    hippo = tmp_path / ".hippocampus"
    _touch(hippo / "hippocampus-index.json", '{"files": {"src/app.py": {}}}\n')
    _touch(hippo / "code-signatures.json", '{"files": {"src/app.py": {"signatures": []}}}\n')
    _touch(hippo / "file-manifest.json", '{"files": {"src/app.py": {"kind": "source"}}}\n')
    _touch(hippo / "structure-prompt.md", "# prompt\n")
    fingerprint = compute_bundle_fingerprint(tmp_path)
    _touch(
        hippo / "bundle-state.json",
        json.dumps({"bundle_fingerprint": fingerprint, "generated_at": datetime.now(timezone.utc).isoformat()}) + "\n",
    )
    _touch(hippo / "architect-metrics.json", "{}\n")

    status = inspect_bundle(tmp_path)

    assert status.ok is False
    assert status.stale_reasons == ["architect-metrics.json missing bundle_fingerprint"]


def test_require_bundle_rejects_mismatched_metrics_fingerprint(tmp_path):
    _write_valid_bundle(tmp_path, metrics_payload={"bundle_fingerprint": "stale"})

    with pytest.raises(RuntimeError, match="stale"):
        require_bundle(tmp_path)


def test_require_bundle_falls_back_to_computed_bundle_fingerprint_without_bundle_state(tmp_path):
    _write_valid_bundle(tmp_path, with_bundle_state=False)

    status = require_bundle(tmp_path)

    assert status.ok is True
    assert status.bundle_state_present is False
    assert status.bundle_fingerprint == status.metrics_fingerprint


def test_require_bundle_uses_bundle_state_as_primary_match_source(tmp_path):
    _write_valid_bundle(tmp_path, metrics_payload={"bundle_fingerprint": "stale"})

    with pytest.raises(RuntimeError, match="bundle-state"):
        require_bundle(tmp_path)


def test_inspect_bundle_marks_added_source_file_as_stale(tmp_path):
    _write_valid_bundle(tmp_path)
    _touch(tmp_path / "src" / "new_file.py", "print('new')\n")

    status = inspect_bundle(tmp_path)

    assert status.ok is False
    assert "file-manifest.json does not match current source tree (added=1, removed=0)" in status.stale_reasons


def test_inspect_bundle_marks_deleted_source_file_as_stale(tmp_path):
    _write_valid_bundle(tmp_path)
    (tmp_path / "src" / "app.py").unlink()

    status = inspect_bundle(tmp_path)

    assert status.ok is False
    assert "file-manifest.json does not match current source tree (added=0, removed=1)" in status.stale_reasons


def test_inspect_bundle_counts_extensionless_code_but_ignores_extensionless_docs(tmp_path):
    _write_valid_bundle(tmp_path)
    _touch(
        tmp_path / "ccb",
        "#!/usr/bin/env python3\n"
        "from cli.entrypoint import run_cli_entrypoint\n"
        "\n"
        "def main():\n"
        "    return run_cli_entrypoint()\n",
    )
    _touch(tmp_path / "LICENSE", "GNU Affero General Public License\n")

    status = inspect_bundle(tmp_path)

    assert status.ok is False
    assert "file-manifest.json does not match current source tree (added=1, removed=0)" in status.stale_reasons


def test_inspect_bundle_respects_manifest_source_scope_for_docs_paths(tmp_path):
    _touch(tmp_path / "src" / "app.py", "print('ok')\n")
    _touch(tmp_path / "docs" / "conf.py", "project = 'demo'\n")
    _touch(tmp_path / "docs" / "Makefile", "html:\n\t@echo html\n")
    hippo = tmp_path / ".hippocampus"
    _touch(hippo / "hippocampus-index.json", '{"files": {"src/app.py": {}}}\n')
    _touch(hippo / "code-signatures.json", '{"files": {"src/app.py": {"signatures": []}}}\n')
    _touch(
        hippo / "file-manifest.json",
        json.dumps(
            {
                "files": {
                    "src/app.py": {"kind": "source"},
                    "docs/conf.py": {"kind": "source"},
                    "docs/Makefile": {"kind": "source"},
                }
            }
        )
        + "\n",
    )
    _touch(hippo / "structure-prompt.md", "# prompt\n")
    fingerprint = compute_bundle_fingerprint(tmp_path)
    generated_at = datetime.now(timezone.utc).isoformat()
    _touch(
        hippo / "bundle-state.json",
        json.dumps({"bundle_fingerprint": fingerprint, "generated_at": generated_at}) + "\n",
    )
    _touch(
        hippo / "architect-metrics.json",
        json.dumps({"bundle_fingerprint": fingerprint, "generated_at": generated_at}) + "\n",
    )

    status = inspect_bundle(tmp_path)

    assert status.ok is True
    assert status.stale_reasons == []


def test_inspect_bundle_respects_hippo_ignore_rules_when_comparing_source_tree(tmp_path):
    _write_valid_bundle(tmp_path)
    _touch(tmp_path / "experimental" / "draft.py", "print('draft')\n")
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[shared]",
                'ignore_paths = ["experimental"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    status = inspect_bundle(tmp_path)

    assert status.ok is True
    assert status.stale_reasons == []


def test_inspect_bundle_ignores_packaging_metadata_directories(tmp_path):
    _write_valid_bundle(tmp_path)
    _touch(tmp_path / "src" / "architec.egg-info" / "PKG-INFO", "Metadata-Version: 2.1\n")

    status = inspect_bundle(tmp_path)

    assert status.ok is True
    assert status.stale_reasons == []


def test_inspect_bundle_marks_updated_source_file_as_stale(tmp_path):
    _write_valid_bundle(tmp_path)
    source = tmp_path / "src" / "app.py"
    future = datetime.now(timezone.utc) + timedelta(seconds=5)
    future_ns = int(future.timestamp() * 1_000_000_000)
    os.utime(source, ns=(future_ns, future_ns))

    status = inspect_bundle(tmp_path)

    assert status.ok is False
    assert "source tree changed after bundle generation (files=1)" in status.stale_reasons
