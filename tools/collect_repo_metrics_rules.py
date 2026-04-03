from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from architec.support.architecture_rules import (  # noqa: E402
    ArchitectureRules,
    RULES_FILE_NAME,
    load_archi_rules as _load_archi_rules,
    path_is_ignored as _path_is_ignored,
)


def load_architecture_rules(root: Path) -> ArchitectureRules:
    return _load_archi_rules(root)


def path_is_ignored(path: Path, *, root: Path, rules: ArchitectureRules | None) -> bool:
    return _path_is_ignored(path.relative_to(root), rules)


__all__ = ["ArchitectureRules", "RULES_FILE_NAME", "load_architecture_rules", "path_is_ignored"]
