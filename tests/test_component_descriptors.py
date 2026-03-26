from __future__ import annotations

import json
from pathlib import Path

from architec.component_descriptors import (
    build_component_descriptors,
    descriptor_search_text,
)
from architec.descriptors.component_descriptors_semantics import descriptor_terms
from architec.descriptors.component_graph import build_component_graph
from architec.orchestrator.component_qa import answer_component_question
from architec.integration.hippo_adapter import HippoSnapshot


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _prepare_snapshot(root: Path) -> HippoSnapshot:
    hippo = root / ".hippocampus"
    _write_json(
        hippo / "architect-metrics.json",
        {
            "findings": [
                {
                    "path": "service/src/payments/engine.py",
                    "severity": "critical",
                    "dimension": "complexity",
                },
                {
                    "path": "service/src/payments/store.py",
                    "severity": "warning",
                    "dimension": "file_size",
                },
            ]
        },
    )
    _write_json(
        hippo / "hippocampus-index.json",
        {
            "files": {
                "service/src/payments/engine.py": {
                    "signatures": [
                        {"name": "__init__", "line": 1, "parent": ""},
                        {"name": "close", "line": 2, "parent": ""},
                        {"name": "PaymentEngine", "line": 10, "parent": ""},
                    ]
                },
                "service/src/payments/store.py": {
                    "signatures": [{"name": "PaymentStore", "line": 12, "parent": ""}]
                },
                "service/tests/test_payments.py": {
                    "signatures": [{"name": "test_payment_flow", "line": 5, "parent": ""}]
                },
                "service/src/orders/router.py": {
                    "signatures": [{"name": "OrderRouter", "line": 8, "parent": ""}]
                },
            },
            "function_dependencies": {
                "service/src/payments/engine.py:PaymentEngine.run": [
                    {
                        "target": "service/src/orders/router.py:OrderRouter.dispatch",
                        "weight": 3,
                    },
                    {
                        "target": "tmp_smoke/main.py:main",
                        "weight": 9,
                    }
                ]
            },
        },
    )
    _write_json(
        hippo / "code-signatures.json",
        {
            "files": {
                "service/src/payments/engine.py": {
                    "signatures": [{"name": "PaymentEngine.run", "line": 18, "parent": "PaymentEngine"}]
                },
                "service/src/payments/store.py": {
                    "signatures": [{"name": "PaymentStore.load", "line": 15, "parent": "PaymentStore"}]
                },
                "service/src/orders/router.py": {
                    "signatures": [{"name": "OrderRouter.dispatch", "line": 20, "parent": "OrderRouter"}]
                },
            }
        },
    )
    (hippo / "structure-prompt.md").write_text("service layout", encoding="utf-8")
    return HippoSnapshot.load(root)


def test_build_component_descriptors_collects_hotspots_symbols_and_neighbors(
    tmp_path: Path,
) -> None:
    snapshot = _prepare_snapshot(tmp_path / "repo")
    descriptors = build_component_descriptors(snapshot)

    payments = descriptors["service:payments"]
    assert payments["file_count"] == 2
    assert "PaymentEngine.run" in payments["primary_symbols"]
    assert "__init__" not in payments["primary_symbols"]
    assert "close" not in payments["primary_symbols"]
    assert payments["findings_by_severity"]["critical"] == 1
    assert payments["test_anchors"] == ["service/tests/test_payments.py"]
    assert payments["dependency_neighbors"][0]["target_component"] == "service:orders"
    assert payments["confidence"] >= 0.7
    assert "payments" in descriptor_search_text(payments).lower()
    assert "tmp_smoke" not in descriptor_search_text(payments).lower()
    assert "orchestration" not in payments["responsibility_summary"].lower()
    assert "pressure points" in payments["responsibility_summary"].lower()


def test_component_graph_aggregates_component_edges(tmp_path: Path) -> None:
    snapshot = _prepare_snapshot(tmp_path / "repo")
    graph = build_component_graph(snapshot)
    assert graph["service:payments"][0]["target_component"] == "service:orders"
    assert graph["service:payments"][0]["weight"] == 3
    assert all(
        edge["target_component"] != "tmp_smoke:main.py" for edge in graph["service:payments"]
    )


def test_component_qa_uses_descriptor_context_for_component_selection(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    _prepare_snapshot(root)
    result = answer_component_question(
        root,
        "How should we stabilize the payments engine and store boundaries?",
        llm_enabled=False,
    )
    assert result["component"] == "service:payments"


def test_component_qa_avoids_tests_component_for_generic_question(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    _prepare_snapshot(root)
    result = answer_component_question(
        root,
        "What should be fixed first in this project?",
        llm_enabled=False,
    )
    assert result["component"] == "service:payments"


def test_component_qa_accepts_preferred_short_name(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    _prepare_snapshot(root)
    result = answer_component_question(
        root,
        "Which boundary needs the most work?",
        component="payments",
        llm_enabled=False,
    )
    assert result["component"] == "service:payments"


def test_descriptor_terms_deduplicates_generic_tokens() -> None:
    descriptor = {
        "component": "service:payments",
        "layer_role": "service-layer",
        "responsibility_summary": "Payments service handles payment orchestration",
        "primary_symbols": ["PaymentEngine.run", "PaymentEngine.run"],
        "files": ["service/src/payments/engine.py"],
    }
    terms = descriptor_terms(descriptor)
    assert "service" not in terms
    assert terms.count("payments") == 1
    assert "paymentengine" in terms


def test_descriptor_search_text_includes_dependency_targets() -> None:
    descriptor = {
        "component": "service:payments",
        "layer_role": "service",
        "responsibility_summary": "Payments flows",
        "primary_symbols": [],
        "descriptor_terms": [],
        "test_anchors": [],
        "dependency_neighbors": [
            {
                "target_component": "service:orders",
                "target_paths": ["service/src/orders/router.py"],
            }
        ],
    }
    search = descriptor_search_text(descriptor)
    assert "service:orders" in search
    assert "service/src/orders/router.py" in search
