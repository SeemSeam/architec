from __future__ import annotations

from pathlib import Path

from architec.support.io_utils import normalize_relpath


EXCLUDED_FINDING_PREFIXES = (
    "hippocampus/vendor/",
    "llm-proxy/docs/",
    "hippocampus/docs/",
    "hippocampus/tmp/",
    ".hippocampus/",
)
GENERIC_SRC_MARKERS = {"src", "lib", "app", "pkg"}
GENERIC_TEST_MARKERS = {"tests", "test"}
ARCHITEC_STEM_GROUPS = {
    "architec:cli": {"__init__", "__main__", "cli"},
    "architec:backend_llm": set(),
    "architec:analysis": {
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
    },
    "architec:orchestration": {
        "orchestrator",
        "orchestrator_batches",
        "orchestrator_llm",
        "orchestrator_test_plan",
        "orchestrator_timing",
        "component_qa",
        "refresh_decider",
    },
    "architec:scoring": {"contract_engine", "hotspot_digest"},
    "architec:reporting": {"report_markdown", "viz_generator"},
    "architec:integration": {
        "hippo_adapter",
        "hippo_bridge",
        "bundle_loader",
        "resource_paths",
        "paths",
        "io_utils",
    },
}
ARCHITEC_PREFIX_GROUPS = (
    ("backend_llm", "architec:backend_llm"),
    ("component_", "architec:scoring"),
    ("component_descriptors", "architec:scoring"),
    ("component_scoring", "architec:scoring"),
    ("scoring_policy", "architec:scoring"),
    ("architecture_report", "architec:reporting"),
)


def component_token(text: str) -> str:
    token = str(text or "").strip()
    if not token:
        return ""
    stem = Path(token).stem
    return stem or token


def is_hidden_path(path: str) -> bool:
    parts = [part for part in normalize_relpath(path).split("/") if part]
    return any(part not in {".", ".."} and part.startswith(".") for part in parts)


def architec_component_for_stem(stem: str) -> str:
    for component, stems in ARCHITEC_STEM_GROUPS.items():
        if stem in stems:
            return component
    for prefix, component in ARCHITEC_PREFIX_GROUPS:
        if stem.startswith(prefix):
            return component
    return f"architec:{stem}"


def _llm_proxy_component(path: str, parts: list[str]) -> str:
    if not path.startswith("llm-proxy/src/llm_proxy/") or len(parts) < 4:
        return ""
    if len(parts) >= 5 and parts[3] == "ops":
        return f"llm-proxy:{parts[3]}/{parts[4]}"
    return f"llm-proxy:{component_token(parts[3])}"


def _architec_prefixed_component(path: str, parts: list[str]) -> str:
    if not path.startswith("src/architec/") or len(parts) < 3:
        return ""
    return architec_component_for_stem(component_token(parts[2]))


def _hippocampus_component(path: str, parts: list[str]) -> str:
    if not path.startswith("hippocampus/src/hippocampus/") or len(parts) < 4:
        return ""
    if len(parts) >= 5 and parts[3] in {
        "tools",
        "memory",
        "nav",
        "query",
        "mcp",
        "llm",
        "parsers",
    }:
        return f"hippocampus:{parts[3]}"
    return f"hippocampus:{component_token(parts[3])}"


def _test_suite_component(path: str, _parts: list[str]) -> str:
    if path.startswith("llm-proxy/tests/"):
        return "llm-proxy:tests"
    if path.startswith("hippocampus/tests/"):
        return "hippocampus:tests"
    return ""


PREFIXED_COMPONENT_RESOLVERS = (
    _llm_proxy_component,
    _architec_prefixed_component,
    _hippocampus_component,
    _test_suite_component,
)


def prefixed_component(path: str, parts: list[str]) -> str:
    for resolver in PREFIXED_COMPONENT_RESOLVERS:
        component = resolver(path, parts)
        if component:
            return component
    return ""


def _generic_test_component(parts: list[str]) -> str:
    if len(parts) >= 2 and parts[1] in GENERIC_TEST_MARKERS:
        return f"{parts[0]}:tests"
    return ""


def _generic_src_component(parts: list[str]) -> str:
    if len(parts) >= 3 and parts[1] in GENERIC_SRC_MARKERS:
        return f"{parts[0]}:{component_token(parts[2])}"
    if len(parts) >= 4 and parts[1] == "packages":
        return f"{parts[0]}:{component_token(parts[2])}"
    return ""


def _fallback_component(parts: list[str]) -> str:
    if len(parts) >= 2:
        return f"{parts[0]}:{component_token(parts[1])}"
    if parts:
        return parts[0]
    return "unknown"


def generic_component(parts: list[str]) -> str:
    return (
        _generic_test_component(parts)
        or _generic_src_component(parts)
        or _fallback_component(parts)
    )
