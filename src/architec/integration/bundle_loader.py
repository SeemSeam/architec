from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from architec.support.architecture_rules import load_architecture_rules, path_is_ignored
from architec.support.io_utils import normalize_relpath, read_json
from architec.support.path_policy import path_kind


REQUIRED_BUNDLE_FILES = (
    ".hippocampus/architect-metrics.json",
    ".hippocampus/hippocampus-index.json",
    ".hippocampus/code-signatures.json",
    ".hippocampus/structure-prompt.md",
)
_BUNDLE_STATE_FILE = ".hippocampus/bundle-state.json"
_FINGERPRINT_BUNDLE_FILES = (
    "hippocampus-index.json",
    "code-signatures.json",
    "file-manifest.json",
)


@dataclass(frozen=True)
class BundleStatus:
    project_root: Path
    present_files: list[str]
    missing_files: list[str]
    stale_reasons: list[str]
    bundle_fingerprint: str = ""
    bundle_state_present: bool = False
    bundle_state_fingerprint: str = ""
    bundle_state_generated_at: str = ""
    metrics_fingerprint: str = ""
    metrics_generated_at: str = ""

    @property
    def ok(self) -> bool:
        return not self.missing_files and not self.stale_reasons


def _manifest_architecture_paths(project_root: Path) -> tuple[bool, set[str]]:
    manifest_path = project_root / ".hippocampus" / "file-manifest.json"
    if not manifest_path.is_file():
        return False, set()
    manifest = read_json(manifest_path, default={})
    if not isinstance(manifest, dict):
        return False, set()
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        return True, set()
    out: set[str] = set()
    for raw_path, item in files.items():
        if not isinstance(item, dict):
            continue
        path = normalize_relpath(str(raw_path or ""))
        if not path:
            continue
        include = item.get("include_in_architecture")
        if include is not None:
            if bool(include):
                out.add(path)
            continue
        kind = str(item.get("kind", "") or "").strip().lower()
        if kind == "source" or (not kind and path_kind(path, probe_root=project_root) == "source"):
            out.add(path)
    return True, out


def _parse_iso_datetime(raw: str) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(probe)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _current_architecture_source_mtimes(project_root: Path) -> dict[str, int]:
    rules = load_architecture_rules(project_root, tool_name="hippo")
    out: dict[str, int] = {}
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        rel = normalize_relpath(path.relative_to(project_root))
        if not rel:
            continue
        if path_is_ignored(rel, rules):
            continue
        if path_kind(rel, probe_root=project_root) != "source":
            continue
        try:
            out[rel] = int(path.stat().st_mtime_ns)
        except OSError:
            continue
    return out


def _source_tree_stale_reasons(project_root: Path, *, reference_generated_at: str) -> list[str]:
    manifest_present, manifest_paths = _manifest_architecture_paths(project_root)
    current_mtimes = _current_architecture_source_mtimes(project_root)
    current_paths = set(current_mtimes)
    reasons: list[str] = []
    if manifest_present and manifest_paths != current_paths:
        added_total = len(current_paths - manifest_paths)
        removed_total = len(manifest_paths - current_paths)
        reasons.append(
            "file-manifest.json does not match current source tree "
            f"(added={added_total}, removed={removed_total})"
        )
    generated_at = _parse_iso_datetime(reference_generated_at)
    if generated_at is None or not current_mtimes:
        return reasons
    reference_ns = int(generated_at.timestamp() * 1_000_000_000)
    changed_total = sum(1 for mtime_ns in current_mtimes.values() if mtime_ns > reference_ns)
    if changed_total > 0:
        reasons.append(
            "source tree changed after bundle generation "
            f"(files={changed_total})"
        )
    return reasons


def compute_bundle_fingerprint(project_root: str | Path) -> str:
    root = Path(project_root).resolve()
    hippo_dir = root / ".hippocampus"
    hasher = hashlib.sha256()
    included = 0
    for name in _FINGERPRINT_BUNDLE_FILES:
        path = hippo_dir / name
        if not path.exists() or not path.is_file():
            continue
        hasher.update(name.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
        included += 1
    if included <= 0:
        return ""
    return hasher.hexdigest()


def inspect_bundle(project_root: str | Path) -> BundleStatus:
    root = Path(project_root).resolve()
    present: list[str] = []
    missing: list[str] = []
    for rel in REQUIRED_BUNDLE_FILES:
        path = root / rel
        if path.exists():
            present.append(rel)
        else:
            missing.append(rel)
    if missing:
        return BundleStatus(
            project_root=root,
            present_files=present,
            missing_files=missing,
            stale_reasons=[],
        )
    bundle_state_path = root / _BUNDLE_STATE_FILE
    bundle_state_present = bundle_state_path.exists()
    if bundle_state_present:
        present.append(_BUNDLE_STATE_FILE)

    metrics = read_json(root / ".hippocampus" / "architect-metrics.json", default={})
    computed_bundle_fingerprint = compute_bundle_fingerprint(root)
    bundle_fingerprint = computed_bundle_fingerprint
    bundle_state_fingerprint = ""
    bundle_state_generated_at = ""
    metrics_fingerprint = ""
    metrics_generated_at = ""
    stale_reasons: list[str] = []
    if bundle_state_present:
        bundle_state = read_json(bundle_state_path, default={})
        if isinstance(bundle_state, dict):
            bundle_state_fingerprint = str(bundle_state.get("bundle_fingerprint", "") or "").strip()
            bundle_state_generated_at = str(bundle_state.get("generated_at", "") or "").strip()
        bundle_fingerprint = bundle_state_fingerprint
        if not bundle_state_fingerprint:
            stale_reasons.append("bundle-state.json missing bundle_fingerprint")
        elif computed_bundle_fingerprint and bundle_state_fingerprint != computed_bundle_fingerprint:
            stale_reasons.append("bundle-state.json does not match current Hippo bundle")
    if isinstance(metrics, dict):
        metrics_fingerprint = str(metrics.get("bundle_fingerprint", "") or "").strip()
        metrics_generated_at = str(metrics.get("generated_at", "") or "").strip()
    if not metrics_fingerprint:
        stale_reasons.append("architect-metrics.json missing bundle_fingerprint")
    elif bundle_fingerprint and metrics_fingerprint != bundle_fingerprint:
        if bundle_state_present:
            stale_reasons.append("architect-metrics.json does not match bundle-state.json")
        else:
            stale_reasons.append("architect-metrics.json does not match current Hippo bundle")
    source_tree_reference = bundle_state_generated_at or metrics_generated_at
    stale_reasons.extend(
        _source_tree_stale_reasons(
            root,
            reference_generated_at=source_tree_reference,
        )
    )

    return BundleStatus(
        project_root=root,
        present_files=present,
        missing_files=missing,
        stale_reasons=stale_reasons,
        bundle_fingerprint=bundle_fingerprint,
        bundle_state_present=bundle_state_present,
        bundle_state_fingerprint=bundle_state_fingerprint,
        bundle_state_generated_at=bundle_state_generated_at,
        metrics_fingerprint=metrics_fingerprint,
        metrics_generated_at=metrics_generated_at,
    )


def require_bundle(project_root: str | Path) -> BundleStatus:
    status = inspect_bundle(project_root)
    if status.missing_files:
        raise FileNotFoundError(
            f"Architec bundle missing required Hippo artifacts under {status.project_root}: "
            + ", ".join(status.missing_files)
        )
    if status.stale_reasons:
        raise RuntimeError(
            f"Architec bundle is stale under {status.project_root}: "
            + "; ".join(status.stale_reasons)
        )
    return status
