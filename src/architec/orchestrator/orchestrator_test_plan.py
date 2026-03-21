from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from ..integration.hippo_adapter import HippoSnapshot

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


def _valid_test_paths(snapshot: HippoSnapshot) -> list[str]:
    root = snapshot.project_root
    return [
        path
        for path in snapshot.first_party_paths()
        if _is_test_path(path) and _is_valid_pytest_target(root, path)
    ]


def _batch_hints(comp_related: list[str], focus_files: list[str], component: str) -> set[str]:
    hints = {Path(path).stem for path in comp_related[:20]}
    hints.update(_component_tokens(component))
    for focus in focus_files:
        hints.update(_component_tokens(Path(str(focus)).stem))
    return hints


def _matching_test_paths(test_paths: list[str], hints: set[str]) -> list[str]:
    matched: list[str] = []
    for test_path in test_paths:
        low = test_path.lower()
        if any(hint and hint in low for hint in list(hints)[:12]):
            matched.append(test_path)
    return matched


def _collect_test_candidates(
    snapshot: HippoSnapshot, batches: list[dict[str, Any]]
) -> list[str]:
    comp_files = snapshot.component_files()
    test_paths = _valid_test_paths(snapshot)

    selected: list[str] = []
    seen: set[str] = set()
    for batch in batches:
        comp = str(batch.get("component", ""))
        comp_related = comp_files.get(comp, [])
        focus_files = batch.get("focus_files", []) if isinstance(batch.get("focus_files"), list) else []
        hints = _batch_hints(comp_related, focus_files, comp)
        for test_path in _matching_test_paths(test_paths, hints):
            if test_path not in seen:
                seen.add(test_path)
                selected.append(test_path)
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
    for candidate in (workspace / "src", root / "src"):
        if candidate.exists() and candidate not in roots:
            roots.append(candidate)
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if len(roots) >= 8:
            break
        if child.is_dir():
            candidate = child / "src"
            if candidate.exists() and candidate not in roots:
                roots.append(candidate)
    if not roots:
        return ""
    joined = ":".join(str(item) for item in roots)
    return f"PYTHONPATH={shlex.quote(joined)}"


def _group_tests_by_workspace(root: Path, tests: list[str]) -> dict[Path, list[str]]:
    grouped: dict[Path, list[str]] = {}
    for test in tests:
        workspace = _workspace_for_test(root, test)
        grouped.setdefault(workspace, []).append(test)
    return grouped


def _relative_group_tests(root: Path, workspace: Path, tests: list[str]) -> list[str]:
    rel_tests: list[str] = []
    for item in tests[:12]:
        abs_test = (root / item).resolve()
        try:
            rel_tests.append(str(abs_test.relative_to(workspace)))
        except Exception:
            rel_tests.append(item)
    return rel_tests


def _build_test_commands(root: Path, tests: list[str]) -> list[str]:
    if not tests:
        return []
    valid_tests = [t for t in tests if _is_valid_pytest_target(root, t)]
    if not valid_tests:
        return []

    grouped = _group_tests_by_workspace(root, valid_tests)
    cmds: list[str] = []
    for workspace, group_tests in sorted(grouped.items(), key=lambda kv: str(kv[0])):
        rel_tests = _relative_group_tests(root, workspace, group_tests)
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
