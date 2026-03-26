from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from architec.integration.bundle_loader import inspect_bundle, require_bundle
from architec.integration.resource_paths import resolve_config_file, tool_script_path


def _hippo_base_command(project_root: Path) -> list[str]:
    hippo_cmd = shutil.which("hippo")
    if hippo_cmd:
        return [hippo_cmd]
    if importlib.util.find_spec("hippocampus.cli") is not None:
        return [sys.executable, "-m", "hippocampus.cli"]
    src_root = project_root / "hippocampus" / "src"
    if src_root.exists():
        return [sys.executable, "-m", "hippocampus.cli"]
    raise FileNotFoundError(
        "Hippo CLI not found. Install hippocampus or ensure `hippo` is on PATH."
    )


def _run(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }


def refresh_bundle_from_hippo(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    before = inspect_bundle(root)
    base_cmd = _hippo_base_command(root)
    steps = [
        [*base_cmd, "init", str(root)],
        [*base_cmd, "sig-extract", str(root)],
        [*base_cmd, "tree", str(root)],
        [*base_cmd, "index", "--no-llm", str(root)],
        [
            *base_cmd,
            "structure-prompt",
            "--profile",
            "map",
            "--no-llm-enhance",
            str(root),
        ],
        [
            sys.executable,
            str(tool_script_path("collect_repo_metrics.py")),
            "--root",
            str(root),
            "--rubric",
            str(resolve_config_file(root, "rubric.json")),
        ],
    ]

    executions: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        print(
            f"refresh [{index}/{len(steps)}] running {' '.join(step)}",
            file=sys.stderr,
            flush=True,
        )
        result = _run(step, cwd=root)
        executions.append(result)
        if int(result["returncode"]) != 0:
            joined = " ".join(step)
            detail = (result["stderr"] or result["stdout"]).strip()
            raise RuntimeError(f"refresh-from-hippo failed for `{joined}`: {detail}")

    after = require_bundle(root)
    return {
        "ok": True,
        "project_root": str(root),
        "before_missing": before.missing_files,
        "after_present": after.present_files,
        "steps": [
            {
                "cmd": " ".join(item["cmd"]),
                "returncode": item["returncode"],
            }
            for item in executions
        ],
    }
