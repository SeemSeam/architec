from __future__ import annotations

from pathlib import Path

from architec.feature.feature_advisor import _rank_candidate_files, suggest_feature_architecture


class _Snapshot:
    def __init__(self) -> None:
        self._component_files = {
            "service:checkout": ["service/src/checkout/engine.py"],
            "app:web": ["app/src/web/router.py"],
        }
        self._paths = [
            "service/src/checkout/engine.py",
            "app/src/web/router.py",
            "docs/architecture.md",
            "vendor/lib/generated.py",
            "service/tests/test_checkout_engine.py",
        ]

    def first_party_paths(self) -> list[str]:
        return list(self._paths)

    @staticmethod
    def signatures_for_file(path: str) -> list[dict]:
        if path.endswith("engine.py"):
            return [{"name": "checkout_engine", "parent": "CheckoutService"}]
        return []

    def component_files(self) -> dict[str, list[str]]:
        return dict(self._component_files)

    @staticmethod
    def component_for_path(path: str) -> str:
        if path.startswith("service/"):
            return "service:checkout"
        return "app:web"

    @staticmethod
    def first_party_findings() -> list[dict]:
        return []


def test_rank_candidate_files_filters_irrelevant_paths() -> None:
    out = _rank_candidate_files(
        _Snapshot(),
        goal="Improve checkout flow and api contracts",
        top_n=10,
    )
    paths = [item["path"] for item in out]
    assert "service/src/checkout/engine.py" in paths
    assert "docs/architecture.md" not in paths
    assert "vendor/lib/generated.py" not in paths


def test_rank_candidate_files_uses_generic_component_tokens() -> None:
    out = _rank_candidate_files(
        _Snapshot(),
        goal="Refactor checkout boundaries and ownership",
        top_n=5,
    )
    first = out[0]
    assert first["component"] == "service:checkout"
    assert any("component:service:checkout" == e for e in first.get("evidence", []))


class _ProjectNoiseSnapshot:
    def __init__(self) -> None:
        self._component_files = {
            "llm-proxy:ops/context": [
                "llm-proxy/src/llm_proxy/ops/context/compaction.py",
                "llm-proxy/src/llm_proxy/ops/context/navigation_runtime.py",
            ],
            "llm-proxy:project_router": [
                "llm-proxy/src/llm_proxy/project_router.py",
            ],
            "llm-proxy:gateway": [
                "llm-proxy/src/llm_proxy/gateway/server.py",
            ],
            "llm-proxy:tests": [
                "llm-proxy/tests/test_gateway_server.py",
            ],
        }
        self._paths = [
            "llm-proxy/src/llm_proxy/ops/context/compaction.py",
            "llm-proxy/src/llm_proxy/ops/context/navigation_runtime.py",
            "llm-proxy/src/llm_proxy/project_router.py",
            "llm-proxy/src/llm_proxy/gateway/server.py",
            "llm-proxy/tests/test_gateway_server.py",
        ]

    def first_party_paths(self) -> list[str]:
        return list(self._paths)

    @staticmethod
    def signatures_for_file(path: str) -> list[dict]:
        if path.endswith("compaction.py"):
            return [{"name": "run_compaction", "parent": "ContextCompactor"}]
        if path.endswith("navigation_runtime.py"):
            return [{"name": "compute_nav_focus", "parent": "NavigationRuntime"}]
        if path.endswith("project_router.py"):
            return [{"name": "route_project_request", "parent": "ProjectRouter"}]
        if path.endswith("server.py"):
            return [{"name": "handle_gateway_request", "parent": "GatewayServer"}]
        if path.endswith("test_gateway_server.py"):
            return [{"name": "test_gateway_server_stability", "parent": "GatewayTests"}]
        return []

    def component_files(self) -> dict[str, list[str]]:
        return dict(self._component_files)

    @staticmethod
    def component_for_path(path: str) -> str:
        if "ops/context" in path:
            return "llm-proxy:ops/context"
        if path.endswith("project_router.py"):
            return "llm-proxy:project_router"
        if "tests/" in path:
            return "llm-proxy:tests"
        return "llm-proxy:gateway"

    @staticmethod
    def first_party_findings() -> list[dict]:
        return [
            {"path": "llm-proxy/src/llm_proxy/ops/context/compaction.py", "severity": "critical"},
            {"path": "llm-proxy/src/llm_proxy/ops/context/compaction.py", "severity": "warning"},
            {"path": "llm-proxy/src/llm_proxy/ops/context/navigation_runtime.py", "severity": "warning"},
        ]


def test_rank_candidate_files_ignores_generic_project_noise() -> None:
    out = _rank_candidate_files(
        _ProjectNoiseSnapshot(),
        goal="Improve stability for current project",
        top_n=5,
    )
    paths = [item["path"] for item in out]
    assert "llm-proxy/src/llm_proxy/project_router.py" not in paths[:1]
    assert "llm-proxy/src/llm_proxy/gateway/server.py" not in paths[:1]


def test_rank_candidate_files_prefers_context_navigation_signals() -> None:
    out = _rank_candidate_files(
        _ProjectNoiseSnapshot(),
        goal="Improve context navigation continuity and compaction stability",
        top_n=5,
    )
    assert out[0]["component"] == "llm-proxy:ops/context"
    assert any(
        item.startswith("hint:llm-proxy:ops/context") or item == "hotspot"
        for item in out[0]["evidence"]
    )


def test_rank_candidate_files_deprioritizes_gateway_for_generic_goal() -> None:
    out = _rank_candidate_files(
        _ProjectNoiseSnapshot(),
        goal="Review architecture hotspots and fix the highest-priority issue",
        top_n=5,
    )
    assert not out or out[0]["component"] != "llm-proxy:gateway"


def test_rank_candidate_files_deprioritizes_tests_for_generic_goal() -> None:
    out = _rank_candidate_files(
        _ProjectNoiseSnapshot(),
        goal="Review architecture hotspots and fix the highest-priority issue",
        top_n=5,
    )
    assert not out or out[0]["component"] != "llm-proxy:tests"


def test_suggest_feature_architecture_uses_hotspot_fallback_without_infra(monkeypatch, tmp_path: Path) -> None:
    snapshot = _ProjectNoiseSnapshot()
    snapshot.project_root = tmp_path

    monkeypatch.setattr(
        "architec.feature.feature_advisor.HippoSnapshot.load",
        lambda _root: snapshot,
    )
    monkeypatch.setattr(
        "architec.feature.feature_advisor.load_or_build_component_descriptors",
        lambda *_a, **_k: {
            "llm-proxy:ops/context": {
                "layer_role": "orchestration",
                "responsibility_summary": "context runtime and continuity",
                "confidence": 0.9,
            },
            "llm-proxy:gateway": {
                "layer_role": "interface_adapter",
                "responsibility_summary": "gateway transport and provider protocol",
                "confidence": 0.9,
            },
            "llm-proxy:tests": {
                "layer_role": "test",
                "responsibility_summary": "test suite",
                "confidence": 0.7,
            },
        },
    )

    out = suggest_feature_architecture(
        tmp_path,
        goal="Review architecture hotspots and fix the highest-priority issue",
        llm_enabled=False,
    )
    targets = [item.get("component") for item in out.get("target_components", [])]
    assert targets
    assert "llm-proxy:gateway" not in targets[:1]
    assert "llm-proxy:tests" not in targets[:1]
