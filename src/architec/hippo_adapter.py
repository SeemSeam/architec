from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io_utils import normalize_relpath, read_json


EXCLUDED_FINDING_PREFIXES = (
    "hippocampus/vendor/",
    "llm-proxy/docs/",
    "hippocampus/docs/",
    "hippocampus/tmp/",
    ".hippocampus/",
)
_GENERIC_SRC_MARKERS = {"src", "lib", "app", "pkg"}
_GENERIC_TEST_MARKERS = {"tests", "test"}


def _component_token(text: str) -> str:
    token = str(text or "").strip()
    if not token:
        return ""
    stem = Path(token).stem
    return stem or token


def _is_hidden_path(path: str) -> bool:
    parts = [part for part in normalize_relpath(path).split("/") if part]
    return any(part not in {".", ".."} and part.startswith(".") for part in parts)


def _architec_component_for_stem(stem: str) -> str:
    if stem in {"__init__", "__main__", "cli"}:
        return "architec:cli"
    if stem.startswith("backend_llm"):
        return "architec:backend_llm"
    if stem in {
        "analysis_runner",
        "history_analyzer",
        "feature_advisor",
        "feature_advisor_llm",
        "feature_advisor_ranking",
        "feature_advisor_ranking_output",
        "feature_advisor_ranking_phase1",
        "feature_advisor_ranking_phase2",
        "feature_advisor_targets",
        "feature_query",
        "feature_query_scoring",
    }:
        return "architec:analysis"
    if stem in {
        "orchestrator",
        "orchestrator_batches",
        "orchestrator_llm",
        "orchestrator_test_plan",
        "orchestrator_timing",
        "component_qa",
        "refresh_decider",
    }:
        return "architec:orchestration"
    if stem.startswith("component_") or stem.startswith("component_descriptors") or stem.startswith("component_scoring"):
        return "architec:scoring"
    if stem.startswith("scoring_policy") or stem in {"contract_engine", "hotspot_digest"}:
        return "architec:scoring"
    if stem.startswith("architecture_report") or stem in {"report_markdown", "viz_generator"}:
        return "architec:reporting"
    if stem in {"hippo_adapter", "hippo_bridge", "bundle_loader", "resource_paths", "paths", "io_utils"}:
        return "architec:integration"
    return f"architec:{stem}"


@dataclass
class HippoSnapshot:
    project_root: Path
    metrics: dict[str, Any]
    index: dict[str, Any]
    signatures: dict[str, Any]
    structure_prompt: str

    @classmethod
    def load(cls, project_root: Path) -> "HippoSnapshot":
        hippo = project_root / ".hippocampus"
        metrics = read_json(hippo / "architect-metrics.json", default={})
        index = read_json(hippo / "hippocampus-index.json", default={})
        signatures = read_json(hippo / "code-signatures.json", default={})
        try:
            structure_prompt = (hippo / "structure-prompt.md").read_text(encoding="utf-8")
        except Exception:
            structure_prompt = ""
        return cls(
            project_root=project_root,
            metrics=metrics if isinstance(metrics, dict) else {},
            index=index if isinstance(index, dict) else {},
            signatures=signatures if isinstance(signatures, dict) else {},
            structure_prompt=structure_prompt,
        )

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
            if _is_hidden_path(path):
                continue
            if any(path.startswith(prefix) for prefix in EXCLUDED_FINDING_PREFIXES):
                continue
            out.append(item)
        return out

    def all_paths(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        index_files = self.index.get("files", {})
        if isinstance(index_files, dict):
            for path in index_files.keys():
                p = normalize_relpath(str(path))
                if p and p not in seen:
                    seen.add(p)
                    out.append(p)
        sig_files = self.signatures.get("files", {})
        if isinstance(sig_files, dict):
            for path in sig_files.keys():
                p = normalize_relpath(str(path))
                if p and p not in seen:
                    seen.add(p)
                    out.append(p)
        return sorted(out)

    def signatures_for_file(self, path: str) -> list[dict[str, Any]]:
        p = normalize_relpath(path)
        sig_files = self.signatures.get("files", {})
        if isinstance(sig_files, dict):
            item = sig_files.get(p)
            if isinstance(item, dict):
                raw = item.get("signatures", [])
                if isinstance(raw, list):
                    return [x for x in raw if isinstance(x, dict)]

        idx_files = self.index.get("files", {})
        if isinstance(idx_files, dict):
            item = idx_files.get(p)
            if isinstance(item, dict):
                raw = item.get("signatures", [])
                if isinstance(raw, list):
                    return [x for x in raw if isinstance(x, dict)]
        return []

    def component_for_path(self, path: str) -> str:
        p = normalize_relpath(path)
        parts = p.split("/")

        if _is_hidden_path(p):
            return "hidden"

        if p.startswith("llm-proxy/src/llm_proxy/") and len(parts) >= 4:
            if len(parts) >= 5 and parts[3] == "ops":
                return f"llm-proxy:{parts[3]}/{parts[4]}"
            return f"llm-proxy:{_component_token(parts[3])}"

        if p.startswith("src/architec/") and len(parts) >= 3:
            return _architec_component_for_stem(_component_token(parts[2]))

        if p.startswith("hippocampus/src/hippocampus/") and len(parts) >= 4:
            if len(parts) >= 5 and parts[3] in {"tools", "memory", "nav", "query", "mcp", "llm", "parsers"}:
                return f"hippocampus:{parts[3]}"
            return f"hippocampus:{_component_token(parts[3])}"

        if p.startswith("llm-proxy/tests/"):
            return "llm-proxy:tests"
        if p.startswith("hippocampus/tests/"):
            return "hippocampus:tests"

        if len(parts) >= 2 and parts[1] in _GENERIC_TEST_MARKERS:
            return f"{parts[0]}:tests"
        if len(parts) >= 3 and parts[1] in _GENERIC_SRC_MARKERS:
            return f"{parts[0]}:{_component_token(parts[2])}"
        if len(parts) >= 4 and parts[1] == "packages":
            return f"{parts[0]}:{_component_token(parts[2])}"

        if len(parts) >= 2:
            return f"{parts[0]}:{_component_token(parts[1])}"
        if parts:
            return parts[0]
        return "unknown"

    def first_party_paths(self) -> list[str]:
        out: list[str] = []
        for path in self.all_paths():
            if _is_hidden_path(path):
                continue
            if any(path.startswith(prefix) for prefix in EXCLUDED_FINDING_PREFIXES):
                continue
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
