from __future__ import annotations

from pathlib import Path

from architec.support.path_policy import is_relevant_arch_path, path_kind


def test_path_kind_probes_extensionless_files(tmp_path: Path) -> None:
    script = tmp_path / "ccb"
    license_file = tmp_path / "LICENSE"
    blob = tmp_path / "payload"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "from cli.entrypoint import run_cli_entrypoint\n"
        "\n"
        "def main():\n"
        "    return run_cli_entrypoint()\n",
        encoding="utf-8",
    )
    license_file.write_text("GNU Affero General Public License\n", encoding="utf-8")
    blob.write_bytes(b"\x00\x01\x02")

    assert path_kind("ccb", probe_root=tmp_path) == "source"
    assert is_relevant_arch_path("ccb", probe_root=tmp_path) is True
    assert path_kind("LICENSE") == "doc"
    assert path_kind("payload", probe_root=tmp_path) == "unsupported"
