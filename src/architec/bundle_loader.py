from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_BUNDLE_FILES = (
    ".hippocampus/architect-metrics.json",
    ".hippocampus/hippocampus-index.json",
    ".hippocampus/code-signatures.json",
    ".hippocampus/structure-prompt.md",
)


@dataclass(frozen=True)
class BundleStatus:
    project_root: Path
    present_files: list[str]
    missing_files: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing_files


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
    return BundleStatus(project_root=root, present_files=present, missing_files=missing)


def require_bundle(project_root: str | Path) -> BundleStatus:
    status = inspect_bundle(project_root)
    if status.ok:
        return status
    raise FileNotFoundError(
        f"Architec bundle missing required Hippo artifacts under {status.project_root}: "
        + ", ".join(status.missing_files)
    )
