#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
DIST = ROOT / "dist"


def read_version() -> str:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return str(payload["project"]["version"])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_artifacts() -> list[Path]:
    return sorted(
        path
        for path in DIST.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS.txt", "RELEASE_NOTES.md"}
    )


def run_build(python_bin: str, clean: bool) -> None:
    if clean:
        shutil.rmtree(DIST, ignore_errors=True)
    subprocess.run([python_bin, "-m", "build", str(ROOT)], check=True)


def run_nuitka_build(python_bin: str) -> None:
    subprocess.run(
        ["bash", str(ROOT / "tools" / "build_nuitka.sh")],
        check=True,
        env={**os.environ, "PYTHON_BIN": python_bin},
    )


def write_checksums(version: str) -> Path:
    artifacts = release_artifacts()
    if not artifacts:
        raise SystemExit("No release artifacts found in dist/")

    lines = [f"# Architec {version} release checksums"]
    for artifact in artifacts:
        lines.append(f"{sha256_file(artifact)}  {artifact.name}")

    target = DIST / "SHA256SUMS.txt"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def write_release_notes(version: str, repo: str) -> Path:
    artifacts = release_artifacts()
    target = DIST / "RELEASE_NOTES.md"
    asset_lines = [f"- `{artifact.name}`" for artifact in artifacts]
    target.write_text(
        "\n".join(
            [
                f"# Architec {version}",
                "",
                "## Installation",
                "",
                "1. Download the compiled binary archive or Python package from this release.",
                "2. Install locally.",
                "3. Run `archi login` to bind the machine to your web account.",
                "4. Run `archi whoami` to confirm the lease is active.",
                "",
                "## Assets",
                "",
                *asset_lines,
                "- `SHA256SUMS.txt`: Release checksums.",
                "",
                "## Notes",
                "",
                "- Distribution is hosted on GitHub Releases.",
                "- Registration, login, seats, and device authorization stay on the website.",
                "- Compiled binary artifacts are preferred when you want to reduce source exposure.",
                "- Compiled artifact names follow archi-<os>-<arch>.(tar.gz|zip).",
                "- The current Linux compiled build excludes the litellm transport path to avoid dragging in torch/matplotlib-class dependencies.",
                "- Cross-platform compiled assets should be built on matching runners, then uploaded into the same release.",
                f"- Release repository: https://github.com/{repo}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build release artifacts and checksums for Architec.")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use for packaging.")
    parser.add_argument("--repo", default="bfly123/architec-releases", help="GitHub release repo for notes.")
    parser.add_argument("--no-clean", action="store_true", help="Keep existing dist/ contents before building.")
    parser.add_argument(
        "--with-nuitka",
        action="store_true",
        help="Also build a compiled standalone binary archive with Nuitka.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = read_version()
    run_build(args.python, clean=not args.no_clean)
    if args.with_nuitka:
        run_nuitka_build(args.python)
    checksum_file = write_checksums(version)
    notes_file = write_release_notes(version, args.repo)
    print(f"Built Architec {version} release artifacts in {DIST}")
    print(f"Wrote {checksum_file.name} and {notes_file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
