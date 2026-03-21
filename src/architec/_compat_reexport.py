from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType
from typing import Any


def reexport(package_name: str, target: str, namespace: dict[str, Any]) -> ModuleType:
    module_name = str(namespace.get("__name__", package_name) or package_name)
    target_module = import_module(target, package_name)
    sys.modules[module_name] = target_module

    parent_name, _, child_name = module_name.rpartition(".")
    if parent_name and child_name:
        parent_module = sys.modules.get(parent_name)
        if parent_module is not None:
            setattr(parent_module, child_name, target_module)

    return target_module
