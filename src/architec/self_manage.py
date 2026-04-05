from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from .support.tls import ensure_default_ca_bundle_env
from .version import current_cli_version


SELF_MANAGE_COMMANDS = {"update", "uninstall"}
DEFAULT_INSTALL_SCRIPT_URL = "https://www.architec.top/downloads/latest/install_prod.sh"
DEFAULT_RELEASE_METADATA_URL = "https://api.github.com/repos/bfly123/architec-releases/releases/latest"
MANAGED_SKILL_NAMES = ("archi-full", "archi-diff", "archi-goal", "archi-advice")


def _urlopen(target: Any, *, timeout: float):
    ensure_default_ca_bundle_env()
    return urlopen(target, timeout=timeout)


def _build_self_manage_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archi", description="Architec maintenance commands")
    subparsers = parser.add_subparsers(dest="self_manage_command", required=True)

    update = subparsers.add_parser("update", help="reinstall the latest public Architec build")
    update.add_argument(
        "--force",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    update.add_argument(
        "--install-script-url",
        default=DEFAULT_INSTALL_SCRIPT_URL,
        help=argparse.SUPPRESS,
    )
    update.add_argument(
        "--release-metadata-url",
        default=DEFAULT_RELEASE_METADATA_URL,
        help=argparse.SUPPRESS,
    )

    uninstall = subparsers.add_parser("uninstall", help="deep-remove the installed Architec launcher, assets, configs, and managed deps")
    uninstall.add_argument(
        "--purge",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    uninstall.add_argument(
        "--remove-deps",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    uninstall.add_argument(
        "--yes",
        action="store_true",
        help="skip the interactive confirmation prompt",
    )
    return parser


def _normalize_version(version: str) -> tuple[int, ...]:
    raw = str(version or "").strip().lower()
    if raw.startswith("v"):
        raw = raw[1:]
    parts: list[int] = []
    for item in raw.split("."):
        if not item:
            continue
        digits = []
        for ch in item:
            if not ch.isdigit():
                break
            digits.append(ch)
        if not digits:
            break
        parts.append(int("".join(digits)))
    return tuple(parts)


def _is_interactive_terminal() -> bool:
    streams = (sys.stdin, sys.stdout, sys.stderr)
    return all(getattr(stream, "isatty", lambda: False)() for stream in streams)


def _fetch_json(url: str) -> dict[str, Any]:
    headers = {"accept": "application/vnd.github+json"}
    token = str(os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")).strip()
    if token:
        headers["authorization"] = f"Bearer {token}"
        headers["x-github-api-version"] = "2022-11-28"
    request = Request(url, headers=headers)
    with _urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _latest_release_version(metadata_url: str) -> str:
    payload = _fetch_json(metadata_url)
    tag_name = str(payload.get("tag_name", "") or "").strip()
    if not tag_name:
        raise RuntimeError(f"latest release metadata did not contain tag_name: {metadata_url}")
    return tag_name[1:] if tag_name.startswith("v") else tag_name


def _download_file(url: str, destination: Path) -> None:
    request = Request(url)
    with _urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


def resolve_version_status(metadata_url: str = DEFAULT_RELEASE_METADATA_URL) -> dict[str, Any]:
    current_version = current_cli_version()
    latest_version = ""
    latest_error = ""
    try:
        latest_version = _latest_release_version(str(metadata_url or DEFAULT_RELEASE_METADATA_URL))
    except Exception as exc:
        latest_error = str(exc)
    upgrade_available = bool(latest_version) and _normalize_version(latest_version) > _normalize_version(current_version)
    return {
        "current_version": current_version,
        "latest_version": latest_version,
        "latest_known": bool(latest_version),
        "upgrade_available": upgrade_available,
        "latest_error": latest_error,
        "recommended_command": "archi update" if upgrade_available else "",
    }


def print_version_status(metadata_url: str = DEFAULT_RELEASE_METADATA_URL) -> int:
    status = resolve_version_status(metadata_url)
    print(f"Architec CLI version: {status['current_version']}")
    latest_version = str(status.get("latest_version", "") or "").strip()
    latest_error = str(status.get("latest_error", "") or "").strip()
    if latest_version:
        print(f"Latest release: {latest_version}")
        if bool(status.get("upgrade_available")):
            print("Update available: yes")
            print(f"Run: {status['recommended_command']}")
        else:
            print("Update available: no")
    else:
        print("Latest release: unknown")
        if latest_error:
            print(f"Latest check failed: {latest_error}")
    return 0


def _run_install_script(script_url: str) -> int:
    with tempfile.TemporaryDirectory(prefix="archi-update-") as tmp:
        script_path = Path(tmp) / "install_prod.sh"
        _download_file(script_url, script_path)
        script_path.chmod(0o755)
        proc = subprocess.run(["bash", str(script_path)], check=False)
        return int(proc.returncode)


def _cmd_update(args: argparse.Namespace) -> int:
    status = resolve_version_status(str(args.release_metadata_url or DEFAULT_RELEASE_METADATA_URL))
    current_version = str(status.get("current_version", "") or "")
    latest_version = str(status.get("latest_version", "") or "")
    latest_error = str(status.get("latest_error", "") or "")

    if latest_version:
        print(f"Current version: {current_version}")
        print(f"Latest version: {latest_version}")
        if not bool(status.get("upgrade_available")):
            print(f"Current version already matches the latest release; reinstalling {latest_version}.")
    else:
        if latest_error:
            print(f"Warning: could not resolve latest release version: {latest_error}", file=sys.stderr)
        print(f"Current version: {current_version}")
        print("Latest version: unknown")
        print("Proceeding with installer refresh because latest metadata could not be verified.")

    print(f"Running installer: {args.install_script_url}")
    result = _run_install_script(str(args.install_script_url or DEFAULT_INSTALL_SCRIPT_URL))
    if result == 0:
        print("Architec update completed.")
    return result


def _installer_paths() -> dict[str, Path]:
    home = Path.home()
    install_base = Path(os.environ.get("ARCHITEC_INSTALL_BASE", home / ".local/architec")).expanduser()
    bin_dir = Path(os.environ.get("ARCHITEC_BIN_DIR", home / ".local/bin")).expanduser()
    return {
        "install_base": install_base,
        "bin_dir": bin_dir,
        "archi_bin": bin_dir / "archi",
        "hippo_bin": bin_dir / "hippo",
        "repomix_bin": bin_dir / "repomix",
        "architec_config": Path(os.environ.get("ARCHITEC_USER_CONFIG_DIR", home / ".architec")).expanduser(),
        "hippocampus_config": Path(os.environ.get("HIPPOCAMPUS_USER_CONFIG_DIR", home / ".hippocampus")).expanduser(),
        "llmgateway_config": Path(os.environ.get("LLMGATEWAY_USER_CONFIG_DIR", home / ".llmgateway")).expanduser(),
        "codex_skills": Path(os.environ.get("ARCHITEC_CODEX_SKILLS_DIR", home / ".codex/skills")).expanduser(),
        "claude_skills": Path(os.environ.get("ARCHITEC_CLAUDE_SKILLS_DIR", home / ".claude/skills")).expanduser(),
    }


def _remove_path(path: Path, removed: list[str]) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    removed.append(str(path))


def _remove_managed_skills(skill_root: Path, removed: list[str]) -> None:
    for name in MANAGED_SKILL_NAMES:
        _remove_path(skill_root / name, removed)


def _remove_tool_if_managed(tool_path: Path, managed_root: Path, removed: list[str]) -> None:
    if not tool_path.exists() and not tool_path.is_symlink():
        return
    try:
        if tool_path.is_symlink():
            target = tool_path.resolve()
            if managed_root in target.parents:
                _remove_path(tool_path, removed)
            return
    except Exception:
        return

    if managed_root.exists() and tool_path.is_file():
        _remove_path(tool_path, removed)


def _confirm_uninstall(args: argparse.Namespace, install_base: Path) -> bool:
    if bool(args.yes):
        return True
    if not _is_interactive_terminal():
        print("Non-interactive uninstall requires --yes.", file=sys.stderr)
        return False
    answer = input(f"Remove Architec from {install_base}? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def _cmd_uninstall(args: argparse.Namespace) -> int:
    paths = _installer_paths()
    install_base = paths["install_base"]
    if not _confirm_uninstall(args, install_base):
        return 2

    removed: list[str] = []
    _remove_path(paths["archi_bin"], removed)
    _remove_tool_if_managed(paths["hippo_bin"], install_base / "python-tools", removed)
    _remove_tool_if_managed(paths["repomix_bin"], install_base / "node-tools", removed)
    _remove_path(install_base, removed)
    _remove_managed_skills(paths["codex_skills"], removed)
    _remove_managed_skills(paths["claude_skills"], removed)

    _remove_path(paths["architec_config"], removed)
    _remove_path(paths["hippocampus_config"], removed)
    _remove_path(paths["llmgateway_config"], removed)

    if removed:
        print("Removed:")
        for item in removed:
            print(f"- {item}")
    else:
        print("No Architec install artifacts were found.")

    print("Config purge: enabled")
    print("Managed Python dependency environment purge: enabled")
    print("Architec uninstall complete.")
    return 0


def handle_self_manage_command(argv: list[str]) -> int | None:
    if not argv:
        return None
    if argv[0] not in SELF_MANAGE_COMMANDS:
        return None
    parser = _build_self_manage_parser()
    args = parser.parse_args(argv)
    if args.self_manage_command == "update":
        return _cmd_update(args)
    if args.self_manage_command == "uninstall":
        return _cmd_uninstall(args)
    return None
