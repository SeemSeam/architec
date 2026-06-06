from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _version() -> str:
    raw = os.environ.get("ARCHITEC_BINARY_VERSION", "").strip()
    if raw:
        return raw
    import architec

    return getattr(architec, "__version__", "")


def _triplet() -> str:
    raw = os.environ.get("ARCHITEC_BINARY_TRIPLET", "").strip()
    if not raw:
        raise SystemExit("ARCHITEC_BINARY_TRIPLET is required")
    return raw


def _pyinstaller_add_data(source: Path, target: str) -> str:
    return f"{source}{os.pathsep}{target}"


def main() -> int:
    version = _version()
    triplet = _triplet()
    if not version:
        raise SystemExit("could not determine architec version")

    from architec.integration import resource_paths

    package_root = resource_paths.package_root()
    build_dir = Path("build") / "standalone"
    entry_path = build_dir / "pyinstaller_archi_entry.py"
    build_dir.mkdir(parents=True, exist_ok=True)
    entry_path.write_text(
        "import os\n"
        "import sys\n\n"
        "if hasattr(sys, '_MEIPASS'):\n"
        "    os.environ.setdefault('ARCHITEC_PACKAGE_ROOT', sys._MEIPASS)\n\n"
        "from architec.cli import main\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n",
        encoding="utf8",
    )

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "archi",
        "--collect-all",
        "architec",
        "--collect-all",
        "llmgateway",
        "--collect-all",
        "hippos",
        "--copy-metadata",
        "architec",
        "--copy-metadata",
        "seemseam_llmgateway",
        "--copy-metadata",
        "seemseam_hippos",
    ]
    for data_name in ("config", "prompts", "tools"):
        data_path = package_root / data_name
        if data_path.exists():
            command.extend(["--add-data", _pyinstaller_add_data(data_path, data_name)])
    command.append(str(entry_path))
    subprocess.run(command, check=True)

    executable_name = "archi.exe" if os.name == "nt" else "archi"
    artifact_name = f"archi-v{version}-{triplet}{'.exe' if os.name == 'nt' else ''}"
    artifact_path = build_dir / artifact_name
    shutil.copy2(Path("dist") / executable_name, artifact_path)
    artifact_path.chmod(0o755)
    print(artifact_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
