from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .hippo_adapter import HippoSnapshot

_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}")


def _is_valid_pytest_target(root: Path, rel_path: str) -> bool:
    path = str(rel_path or "").strip()
    if not path:
        return False
    abs_path = (root / path).resolve()
    if not abs_path.exists():
        return False
    if abs_path.is_dir():
        return True
    if abs_path.suffix != ".py":
        return False
    name = abs_path.name
    return bool(name.startswith("test_") or name.endswith("_test.py"))


def _is_test_path(rel_path: str) -> bool:
    parts = [seg.lower() for seg in str(rel_path or "").strip().split("/") if seg]
    if not parts:
        return False
    if parts[0] in {"tests", "test"}:
        return True
    return any(seg in {"tests", "test"} for seg in parts[1:])


def _component_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for token in _TOKEN_RE.findall(str(text or "").lower()):
        if token not in {"tests", "test", "src", "core"}:
            out.add(token)
    return out


def _collect_test_candidates(
    snapshot: HippoSnapshot, batches: list[dict[str, Any]]
) -> list[str]:
    comp_files = snapshot.component_files()
    root = snapshot.project_root
    test_paths = [
        p
        for p in snapshot.first_party_paths()
        if _is_test_path(p)
        and _is_valid_pytest_target(root, p)
    ]

    selected: list[str] = []
    seen: set[str] = set()
    for batch in batches:
        comp = str(batch.get("component", ""))
        comp_related = comp_files.get(comp, [])
        hints = {Path(p).stem for p in comp_related[:20]}
        hints.update(_component_tokens(comp))
        for focus in batch.get("focus_files", []) if isinstance(batch.get("focus_files"), list) else []:
            hints.update(_component_tokens(Path(str(focus)).stem))
        for tp in test_paths:
            low = tp.lower()
            matched = any(h and h in low for h in list(hints)[:12])
            if matched and tp not in seen:
                seen.add(tp)
                selected.append(tp)
        if len(selected) >= 20:
            break

    return (selected or test_paths[:10])[:20]


def _workspace_for_test(root: Path, rel_test: str) -> Path:
    parts = [seg for seg in str(rel_test or "").split("/") if seg]
    if parts and (root / parts[0]).exists():
        return root / parts[0]
    return root


def _build_pythonpath(root: Path, workspace: Path) -> str:
    roots: list[Path] = []
    ws_src = workspace / "src"
    if ws_src.exists():
        roots.append(ws_src)
    root_src = root / "src"
    if root_src.exists() and root_src not in roots:
        roots.append(root_src)
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if len(roots) >= 8:
            break
        if not child.is_dir():
            continue
        cand = child / "src"
        if cand.exists() and cand not in roots:
            roots.append(cand)
    if not roots:
        return ""
    joined = ":".join(str(item) for item in roots)
    return f"PYTHONPATH={shlex.quote(joined)}"


def _build_test_commands(root: Path, tests: list[str]) -> list[str]:
    if not tests:
        return []
    valid_tests = [t for t in tests if _is_valid_pytest_target(root, t)]
    if not valid_tests:
        return []

    grouped: dict[Path, list[str]] = {}
    for test in valid_tests:
        workspace = _workspace_for_test(root, test)
        grouped.setdefault(workspace, []).append(test)
    cmds: list[str] = []
    for workspace, group_tests in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        rel_tests: list[str] = []
        for item in group_tests[:12]:
            abs_test = (root / item).resolve()
            try:
                rel_tests.append(str(abs_test.relative_to(workspace)))
            except Exception:
                rel_tests.append(item)
        chunk = " ".join(shlex.quote(p) for p in rel_tests)
        py = _build_pythonpath(root, workspace)
        if py:
            cmds.append(
                f"cd {shlex.quote(str(workspace))} && {py} pytest -q {chunk}"
            )
        else:
            cmds.append(f"cd {shlex.quote(str(workspace))} && pytest -q {chunk}")
    return cmds


def _run_test_commands(commands: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for cmd in commands:
        proc = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        results.append(
            {
                "command": cmd,
                "exit_code": proc.returncode,
                "passed": proc.returncode == 0,
                "output_tail": "\n".join(out.splitlines()[-80:]),
            }
        )
    return results
