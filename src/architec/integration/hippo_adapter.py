from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from architec.integration.hippo_adapter_paths import (
    EXCLUDED_FINDING_PREFIXES,
    generic_component,
    is_hidden_path,
    prefixed_component,
)
from architec.integration.bundle_loader import bundle_file
from architec.integration.hippo_adapter_snapshot import (
    add_unique_paths,
    signatures_from_file_map,
)
from architec.support.io_utils import normalize_relpath, read_json
from architec.support.path_policy import is_relevant_arch_path, path_kind


@dataclass
class HippoSnapshot:
    project_root: Path
    metrics: dict[str, Any]
    index: dict[str, Any]
    signatures: dict[str, Any]
    structure_prompt: str
    file_manifest: dict[str, Any] | None = None

    @classmethod
    def load(cls, project_root: Path) -> "HippoSnapshot":
        metrics = read_json(bundle_file(project_root, "architect-metrics.json"), default={})
        index = read_json(bundle_file(project_root, "index"), default={})
        signatures = read_json(bundle_file(project_root, "code-signatures.json"), default={})
        file_manifest = read_json(bundle_file(project_root, "file-manifest.json"), default={})
        try:
            structure_prompt = bundle_file(project_root, "structure-prompt.md").read_text(encoding="utf-8")
        except Exception:
            structure_prompt = ""
        return cls(
            project_root=project_root,
            metrics=metrics if isinstance(metrics, dict) else {},
            index=index if isinstance(index, dict) else {},
            signatures=signatures if isinstance(signatures, dict) else {},
            structure_prompt=structure_prompt,
            file_manifest=file_manifest if isinstance(file_manifest, dict) else {},
        )

    def _manifest_files(self) -> dict[str, dict[str, Any]]:
        raw = (self.file_manifest or {}).get("files", {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for path, item in raw.items():
            normalized = normalize_relpath(str(path))
            if normalized and isinstance(item, dict):
                out[normalized] = item
        return out

    def file_record(self, path: str) -> dict[str, Any]:
        return self._manifest_files().get(normalize_relpath(path), {})

    def file_kind(self, path: str) -> str:
        record = self.file_record(path)
        kind = str(record.get("kind", "") or "").strip()
        if kind:
            return kind
        return path_kind(path, probe_root=self.project_root)

    def is_architecture_path(self, path: str) -> bool:
        record = self.file_record(path)
        if "include_in_architecture" in record:
            return bool(record.get("include_in_architecture"))
        return is_relevant_arch_path(path, probe_root=self.project_root)

    def is_test_support_path(self, path: str) -> bool:
        record = self.file_record(path)
        if "include_in_test_support" in record:
            return bool(record.get("include_in_test_support"))
        return self.file_kind(path) == "test"

    def findings(self) -> list[dict[str, Any]]:
        raw = self.metrics.get("findings", [])
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def first_party_findings(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in self.findings():
            path = normalize_relpath(str(item.get("path", "")))
            if not path:
                continue
            if is_hidden_path(path):
                continue
            if not self.is_architecture_path(path):
                continue
            if any(path.startswith(prefix) for prefix in EXCLUDED_FINDING_PREFIXES):
                continue
            out.append(item)
        return out

    def all_paths(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        add_unique_paths(out, seen, self._manifest_files())
        add_unique_paths(out, seen, self.index.get("files", {}))
        add_unique_paths(out, seen, self.signatures.get("files", {}))
        return sorted(out)

    def signatures_for_file(self, path: str) -> list[dict[str, Any]]:
        p = normalize_relpath(path)
        return signatures_from_file_map(self.signatures.get("files", {}), p) or signatures_from_file_map(
            self.index.get("files", {}),
            p,
        )

    def component_for_path(self, path: str) -> str:
        p = normalize_relpath(path)
        parts = p.split("/")

        if is_hidden_path(p):
            return "hidden"
        prefixed = prefixed_component(p, parts)
        if prefixed:
            return prefixed
        return generic_component(parts)

    def first_party_paths(self) -> list[str]:
        out: list[str] = []
        for path in self.all_paths():
            if is_hidden_path(path):
                continue
            if not self.is_architecture_path(path):
                continue
            if any(path.startswith(prefix) for prefix in EXCLUDED_FINDING_PREFIXES):
                continue
            out.append(path)
        return out

    def test_support_paths(self) -> list[str]:
        out: list[str] = []
        for path in self.all_paths():
            if is_hidden_path(path):
                continue
            if any(path.startswith(prefix) for prefix in EXCLUDED_FINDING_PREFIXES):
                continue
            if self.is_test_support_path(path):
                out.append(path)
        return out

    def component_files(self) -> dict[str, list[str]]:
        comp: dict[str, list[str]] = {}
        for path in self.first_party_paths():
            key = self.component_for_path(path)
            comp.setdefault(key, []).append(path)
        for files in comp.values():
            files.sort()
        return dict(sorted(comp.items(), key=lambda kv: kv[0]))

    def function_dependencies(self) -> dict[str, list[dict[str, Any]]]:
        raw = self.index.get("function_dependencies", {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, list[dict[str, Any]]] = {}
        for source, edges in raw.items():
            if not isinstance(source, str) or not isinstance(edges, list):
                continue
            out[source] = [e for e in edges if isinstance(e, dict)]
        return out


def split_symbol_ref(ref: str) -> tuple[str, str]:
    text = normalize_relpath(ref)
    if not text:
        return "", ""
    if ":" not in text:
        return text, ""
    path, symbol = text.rsplit(":", 1)
    return normalize_relpath(path), str(symbol or "").strip()
