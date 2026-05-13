from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from architec.scoring.component_scoring_scope import changed_files_from_env_scope
from architec.support.io_utils import normalize_relpath, safe_int


CHANGED_FILES_SCOPE_ENV = "ARCH_SCORE_CHANGED_FILES"


def run_git(root: Path, args: list[str], *, strict: bool = False) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        if strict:
            message = (proc.stderr or proc.stdout or "").strip()
            command = "git " + " ".join(args)
            raise RuntimeError(f"git range error while running `{command}`: {message}")
        return ""
    return proc.stdout or ""


def parse_numstat(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in (text or "").splitlines():
        parts = raw.split("\t")
        if len(parts) < 3:
            continue
        added = safe_int(parts[0], 0)
        deleted = safe_int(parts[1], 0)
        path = normalize_relpath(parts[2])
        if " => " in path:
            path = normalize_relpath(
                path.split(" => ")[-1].replace("}", "").replace("{", "")
            )
        out.append({"path": path, "added": added, "deleted": deleted})
    return out


def changed_files_from_env() -> list[dict[str, Any]]:
    raw = str(os.environ.get(CHANGED_FILES_SCOPE_ENV, "") or "").strip()
    if not raw:
        return []
    return changed_files_from_env_scope(raw, normalize_path=normalize_relpath)


def changed_files(root: Path, base: str | None, head: str | None) -> list[dict[str, Any]]:
    scoped = changed_files_from_env()
    if scoped:
        return scoped

    if base and head:
        return parse_numstat(run_git(root, ["diff", "--numstat", f"{base}...{head}"], strict=True))

    rows = parse_numstat(run_git(root, ["diff", "--numstat", "HEAD"]))
    if rows:
        return rows

    status = run_git(root, ["status", "--porcelain"])
    fallback: list[dict[str, Any]] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = normalize_relpath(line[3:])
        fallback.append({"path": path, "added": 0, "deleted": 0})
    return fallback
