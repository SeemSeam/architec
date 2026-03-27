from __future__ import annotations

from pathlib import Path

import pytest

from architec.orchestrator import (
    _build_test_command_specs,
    _build_test_commands,
    _is_valid_pytest_target,
    orchestrate_analysis_modify_test,
)
from architec.orchestrator.orchestrator_report import llm_orchestration_payload
from architec.orchestrator.orchestrator_test_plan import _collect_test_candidates, _is_test_path
from architec.support.llm_guard import ArchitectLLMUnavailableError


def test_is_valid_pytest_target_filters_missing_and_non_test_files(tmp_path: Path) -> None:
    tests_dir = tmp_path / "hippocampus" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tests_dir / "conftest.py").write_text("", encoding="utf-8")
    (tests_dir / "benchmark_trim.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    assert _is_valid_pytest_target(tmp_path, "hippocampus/tests/test_ok.py") is True
    assert _is_valid_pytest_target(tmp_path, "hippocampus/tests/conftest.py") is False
    assert _is_valid_pytest_target(tmp_path, "hippocampus/tests/benchmark_trim.sh") is False
    assert _is_valid_pytest_target(tmp_path, "hippocampus/tests/missing_test.py") is False


def test_build_test_commands_only_keeps_valid_pytest_targets(tmp_path: Path) -> None:
    llm_tests = tmp_path / "llm-proxy" / "tests"
    hippo_tests = tmp_path / "hippocampus" / "tests"
    llm_tests.mkdir(parents=True)
    hippo_tests.mkdir(parents=True)
    (llm_tests / "test_gateway_server.py").write_text(
        "def test_gateway_server():\n    assert True\n",
        encoding="utf-8",
    )
    (hippo_tests / "test_nav.py").write_text("def test_nav():\n    assert True\n", encoding="utf-8")
    (hippo_tests / "benchmark_trim.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    cmds = _build_test_commands(
        tmp_path,
        [
            "llm-proxy/tests/test_gateway_server.py",
            "hippocampus/tests/benchmark_trim.sh",
            "hippocampus/tests/test_nav.py",
        ],
    )
    rendered = "\n".join(cmds)
    assert "benchmark_trim.sh" not in rendered
    assert "test_gateway_server.py" in rendered
    assert "test_nav.py" in rendered


def test_build_test_commands_generic_workspace_grouping(tmp_path: Path) -> None:
    app_tests = tmp_path / "app" / "tests"
    svc_tests = tmp_path / "service" / "tests"
    (tmp_path / "app" / "src").mkdir(parents=True)
    (tmp_path / "service" / "src").mkdir(parents=True)
    app_tests.mkdir(parents=True)
    svc_tests.mkdir(parents=True)
    (app_tests / "test_api.py").write_text("def test_api():\n    assert True\n", encoding="utf-8")
    (svc_tests / "test_worker.py").write_text(
        "def test_worker():\n    assert True\n", encoding="utf-8"
    )

    cmds = _build_test_commands(
        tmp_path,
        [
            "app/tests/test_api.py",
            "service/tests/test_worker.py",
        ],
    )
    rendered = "\n".join(cmds)
    assert "cd " in rendered
    assert str(tmp_path / "app") in rendered
    assert str(tmp_path / "service") in rendered
    assert "test_api.py" in rendered
    assert "test_worker.py" in rendered


def test_collect_test_candidates_generic_component_match(tmp_path: Path) -> None:
    service_tests = tmp_path / "service" / "tests"
    worker_tests = tmp_path / "worker" / "tests"
    service_tests.mkdir(parents=True)
    worker_tests.mkdir(parents=True)
    (service_tests / "test_checkout_api.py").write_text(
        "def test_checkout_api():\n    assert True\n", encoding="utf-8"
    )
    (worker_tests / "test_jobs_runner.py").write_text(
        "def test_jobs_runner():\n    assert True\n", encoding="utf-8"
    )

    class _Snapshot:
        project_root = tmp_path

        @staticmethod
        def component_files() -> dict[str, list[str]]:
            return {
                "service:checkout": ["service/src/checkout_api.py"],
                "worker:jobs": ["worker/src/jobs_runner.py"],
            }

        @staticmethod
        def first_party_paths() -> list[str]:
            return [
                "service/tests/test_checkout_api.py",
                "worker/tests/test_jobs_runner.py",
            ]

    selected = _collect_test_candidates(
        _Snapshot(),
        [{"component": "service:checkout", "focus_files": ["service/src/checkout_api.py"]}],
    )
    assert "service/tests/test_checkout_api.py" in selected
    assert "worker/tests/test_jobs_runner.py" not in selected


def test_is_test_path_covers_multilanguage_patterns() -> None:
    assert _is_test_path("frontend/src/app.spec.ts") is True
    assert _is_test_path("backend/tests/api_test.go") is True
    assert _is_test_path("pkg/tests/vector_test.f90") is True
    assert _is_test_path("src/main.py") is False


def test_build_test_commands_supports_node_go_rust_and_native(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    backend = tmp_path / "backend"
    rustsvc = tmp_path / "rustsvc"
    native = tmp_path / "native"

    (frontend / "src").mkdir(parents=True)
    (frontend / "tests").mkdir(parents=True)
    (backend / "pkg").mkdir(parents=True)
    (backend / "tests").mkdir(parents=True)
    (rustsvc / "tests").mkdir(parents=True)
    (native / "tests").mkdir(parents=True)

    (frontend / "package.json").write_text('{"devDependencies":{"vitest":"^1.0.0"}}', encoding="utf-8")
    (frontend / "tests" / "app.spec.ts").write_text("it('x', () => {})\n", encoding="utf-8")
    (backend / "tests" / "api_test.go").write_text("package tests\n", encoding="utf-8")
    (rustsvc / "tests" / "flow.rs").write_text("#[test]\nfn flow() {}\n", encoding="utf-8")
    (native / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.20)\n", encoding="utf-8")
    (native / "tests" / "solver_test.f90").write_text("program solver_test\nend program\n", encoding="utf-8")

    cmds = _build_test_commands(
        tmp_path,
        [
            "frontend/tests/app.spec.ts",
            "backend/tests/api_test.go",
            "rustsvc/tests/flow.rs",
            "native/tests/solver_test.f90",
        ],
    )
    rendered = "\n".join(cmds)
    assert "vitest run" in rendered
    assert "go test ./tests" in rendered
    assert "cargo test --test flow" in rendered
    assert "ctest --output-on-failure" in rendered


def test_build_test_commands_supports_jvm_and_dotnet(tmp_path: Path) -> None:
    jvm = tmp_path / "jvmapp"
    dotnet = tmp_path / "dotnetapp"
    (jvm / "src" / "test" / "java" / "com" / "acme").mkdir(parents=True)
    (dotnet / "tests").mkdir(parents=True)
    (jvm / "gradlew").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (jvm / "src" / "test" / "java" / "com" / "acme" / "CheckoutServiceTest.java").write_text("class CheckoutServiceTest {}\n", encoding="utf-8")
    (dotnet / "tests" / "CheckoutTests.cs").write_text("class CheckoutTests {}\n", encoding="utf-8")

    cmds = _build_test_commands(
        tmp_path,
        [
            "jvmapp/src/test/java/com/acme/CheckoutServiceTest.java",
            "dotnetapp/tests/CheckoutTests.cs",
        ],
    )
    rendered = "\n".join(cmds)
    assert "./gradlew test --tests CheckoutServiceTest" in rendered
    assert "dotnet test --filter" in rendered


def test_build_test_command_specs_include_language_runner_and_workspace(tmp_path: Path) -> None:
    frontend = tmp_path / "frontend"
    (frontend / "tests").mkdir(parents=True)
    (frontend / "package.json").write_text('{"devDependencies":{"vitest":"^1.0.0"}}', encoding="utf-8")
    (frontend / "tests" / "app.spec.ts").write_text("it('x', () => {})\n", encoding="utf-8")

    specs = _build_test_command_specs(tmp_path, ["frontend/tests/app.spec.ts"])

    assert len(specs) == 1
    assert specs[0]["language"] == "javascript/typescript"
    assert specs[0]["runner"] == "vitest"
    assert specs[0]["workspace"] == str(frontend)
    assert specs[0]["tests"] == ["tests/app.spec.ts"]
    assert "vitest run" in specs[0]["command"]


def test_llm_orchestration_payload_keeps_backward_commands_and_structured_specs() -> None:
    payload = llm_orchestration_payload(
        goal="stabilize service boundaries",
        question="what should be tested first?",
        batches=[
            {
                "batch": 1,
                "component": "frontend:checkout",
                "priority": "high",
                "focus_files": ["frontend/src/checkout.ts", "frontend/src/cart.ts"],
            }
        ],
        test_commands=["cd /repo/frontend && npx vitest run tests/app.spec.ts"],
        test_command_specs=[
            {
                "language": "javascript/typescript",
                "runner": "vitest",
                "workspace": "/repo/frontend",
                "command": "cd /repo/frontend && npx vitest run tests/app.spec.ts",
                "tests": ["tests/app.spec.ts"],
            }
        ],
    )

    assert payload["test_commands"] == ["cd /repo/frontend && npx vitest run tests/app.spec.ts"]
    assert payload["test_command_specs"] == [
        {
            "language": "javascript/typescript",
            "runner": "vitest",
            "workspace": "/repo/frontend",
            "command": "cd /repo/frontend && npx vitest run tests/app.spec.ts",
            "tests": ["tests/app.spec.ts"],
        }
    ]


def test_orchestrate_emits_minimal_hotspot_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "architec.orchestrator.analyze_history_and_iterate",
        lambda root, llm_enabled=True: {
            "summary": {},
            "full_score": {"score": 70.0, "recommendation": "needs_changes"},
            "hotspots": [
                {"path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py", "critical": 2, "warning": 3, "score": 44.0}
            ],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.suggest_feature_architecture",
        lambda root, goal, llm_enabled=True: {
            "target_components": [
                {
                    "component": "llm-proxy:ops/context",
                    "score": 30,
                    "evidence_paths": ["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"],
                }
            ]
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.score_changed_components",
        lambda root, base=None, head=None, llm_enabled=True: {
            "summary": {},
            "incremental_score": {"score": 45.0, "recommendation": "block"},
            "components": [
                {
                    "component": "llm-proxy:ops/context",
                    "score": 20.0,
                    "hotspot_refs": [
                        {"path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py", "score": 50.0, "critical": 2, "warning": 3}
                    ],
                }
            ],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.answer_component_question",
        lambda root, question, component=None, llm_enabled=True: {"component": "llm-proxy:ops/context"},
    )
    monkeypatch.setattr(
        "architec.orchestrator.load_or_build_component_descriptors",
        lambda *args, **kwargs: {
            "llm-proxy:ops/context": {
                "layer_role": "orchestration",
                "confidence": 0.88,
                "dependency_neighbors": [
                    {"target_component": "llm-proxy:gateway"},
                    {"target_component": "hippocampus:nav"},
                ],
                "files": [
                    "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
                    "llm-proxy/src/llm_proxy/ops/context/store.py",
                ],
            }
        },
    )
    monkeypatch.setattr("architec.orchestrator._collect_test_candidates", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_commands", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_command_specs", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_command_specs", lambda *_a, **_k: [])

    out = orchestrate_analysis_modify_test(
        tmp_path,
        goal="improve architecture quality and reduce high-risk hotspots",
        question="what should be fixed first?",
        llm_enabled=False,
        run_tests=False,
    )
    assert "hotspot_minimal" in out.get("artifacts", {})
    assert "architecture_report_md" in out.get("artifacts", {})
    assert "runtime" in out
    assert "history" in out["runtime"]["timings"]
    assert "architecture_report" in out["runtime"]["timings"]
    assert out["change_batches"][0]["why"]["layer_role"] == "orchestration"
    assert out["change_batches"][0]["why"]["descriptor_confidence"] == 0.88
    assert "llm-proxy:gateway" in out["change_batches"][0]["why"]["neighbor_components"]
    assert out["test_plan"]["command_specs"] == []
    digest_path = tmp_path / ".architec" / "architec-hotspots-topk.json"
    report_path = tmp_path / ".architec" / "architec-architecture-report.md"
    assert digest_path.exists()
    assert report_path.exists()


def test_orchestrate_hard_fails_when_llm_enhancement_raises(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "architec.orchestrator.analyze_history_and_iterate",
        lambda root, llm_enabled=True: {
            "summary": {},
            "full_score": {"score": 70.0, "recommendation": "needs_changes"},
            "hotspots": [],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.suggest_feature_architecture",
        lambda root, goal, llm_enabled=True: {"target_components": []},
    )
    monkeypatch.setattr(
        "architec.orchestrator.score_changed_components",
        lambda root, base=None, head=None, llm_enabled=True: {
            "summary": {},
            "incremental_score": {"score": 45.0, "recommendation": "block"},
            "components": [],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.answer_component_question",
        lambda root, question, component=None, llm_enabled=True: {"component": "x"},
    )
    monkeypatch.setattr("architec.orchestrator._collect_test_candidates", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_commands", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_command_specs", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_command_specs", lambda *_a, **_k: [])
    monkeypatch.setattr(
        "architec.orchestrator._llm_orchestration_enhancement",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("llm blocked")),
    )

    with pytest.raises(ArchitectLLMUnavailableError):
        orchestrate_analysis_modify_test(
            tmp_path,
            goal="improve architecture quality",
            question="what should be fixed first?",
            llm_enabled=True,
            run_tests=False,
        )


def test_orchestrate_falls_back_to_descriptor_component_when_feature_targets_empty(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "architec.orchestrator.analyze_history_and_iterate",
        lambda root, llm_enabled=True: {
            "summary": {},
            "full_score": {"score": 70.0, "recommendation": "needs_changes"},
            "hotspots": [
                {
                    "path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
                    "critical": 2,
                    "warning": 3,
                    "score": 44.0,
                }
            ],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.suggest_feature_architecture",
        lambda root, goal, llm_enabled=True: {"target_components": []},
    )
    monkeypatch.setattr(
        "architec.orchestrator.score_changed_components",
        lambda root, base=None, head=None, llm_enabled=True: {
            "summary": {},
            "incremental_score": {"score": 35.0, "recommendation": "block"},
            "components": [
                {
                    "component": "llm-proxy:ops/context",
                    "score": 22.0,
                    "recommendation": "block",
                    "changed_files": ["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"],
                    "findings": {"critical": 2},
                }
            ],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.answer_component_question",
        lambda root, question, component=None, llm_enabled=True: {"component": "llm-proxy:ops/context"},
    )
    monkeypatch.setattr(
        "architec.orchestrator.load_or_build_component_descriptors",
        lambda *args, **kwargs: {
            "llm-proxy:ops/context": {
                "layer_role": "orchestration",
                "confidence": 0.91,
                "files": [
                    "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
                    "llm-proxy/src/llm_proxy/ops/context/store.py",
                ],
            }
        },
    )
    monkeypatch.setattr("architec.orchestrator._collect_test_candidates", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_commands", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_command_specs", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_command_specs", lambda *_a, **_k: [])

    out = orchestrate_analysis_modify_test(
        tmp_path,
        goal="review architecture hotspots",
        question="what should be fixed first?",
        llm_enabled=False,
        run_tests=False,
    )
    assert out["change_batches"][0]["component"] == "llm-proxy:ops/context"
    assert out["change_batches"][0]["why"]["note"].startswith("fallback from scoring/qa")
    assert out["change_batches"][0]["why"]["descriptor_confidence"] == 0.91


def test_orchestrate_generic_goal_skips_gateway_infra_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "architec.orchestrator.analyze_history_and_iterate",
        lambda root, llm_enabled=True: {
            "summary": {},
            "full_score": {"score": 70.0, "recommendation": "needs_changes"},
            "hotspots": [],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.suggest_feature_architecture",
        lambda root, goal, llm_enabled=True: {"target_components": []},
    )
    monkeypatch.setattr(
        "architec.orchestrator.score_changed_components",
        lambda root, base=None, head=None, llm_enabled=True: {
            "summary": {},
            "incremental_score": {"score": 30.0, "recommendation": "block"},
            "components": [
                {
                    "component": "llm-proxy:gateway",
                    "score": 17.0,
                    "recommendation": "block",
                    "changed_files": ["llm-proxy/src/llm_proxy/gateway/server.py"],
                    "findings": {"critical": 2},
                },
                {
                    "component": "llm-proxy:ops/context",
                    "score": 31.0,
                    "recommendation": "block",
                    "changed_files": ["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"],
                    "findings": {"critical": 2},
                },
            ],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.answer_component_question",
        lambda root, question, component=None, llm_enabled=True: {"component": "llm-proxy:gateway"},
    )
    monkeypatch.setattr(
        "architec.orchestrator.load_or_build_component_descriptors",
        lambda *args, **kwargs: {
            "llm-proxy:gateway": {
                "layer_role": "interface_adapter",
                "confidence": 0.9,
                "files": ["llm-proxy/src/llm_proxy/gateway/server.py"],
            },
            "llm-proxy:ops/context": {
                "layer_role": "orchestration",
                "confidence": 0.9,
                "files": ["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"],
            },
        },
    )
    monkeypatch.setattr("architec.orchestrator._collect_test_candidates", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_commands", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_command_specs", lambda *_a, **_k: [])

    out = orchestrate_analysis_modify_test(
        tmp_path,
        goal="Review architecture hotspots and fix the highest-priority issue",
        question="What should be fixed first?",
        llm_enabled=False,
        run_tests=False,
    )
    assert out["change_batches"][0]["component"] == "llm-proxy:ops/context"


def test_orchestrate_generic_goal_skips_tests_in_feature_targets(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "architec.orchestrator.analyze_history_and_iterate",
        lambda root, llm_enabled=True: {
            "summary": {},
            "full_score": {"score": 70.0, "recommendation": "needs_changes"},
            "hotspots": [
                {
                    "path": "llm-proxy/src/llm_proxy/ops/context/lifecycle.py",
                    "critical": 1,
                    "warning": 1,
                    "score": 24.0,
                }
            ],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.suggest_feature_architecture",
        lambda root, goal, llm_enabled=True: {
            "target_components": [
                {
                    "component": "llm-proxy:tests",
                    "score": 42.0,
                    "evidence_paths": ["llm-proxy/tests/test_gateway_server.py"],
                },
                {
                    "component": "llm-proxy:ops/context",
                    "score": 35.0,
                    "evidence_paths": ["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"],
                },
            ]
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.score_changed_components",
        lambda root, base=None, head=None, llm_enabled=True: {
            "summary": {},
            "incremental_score": {"score": 35.0, "recommendation": "block"},
            "components": [
                {
                    "component": "llm-proxy:ops/context",
                    "score": 22.0,
                    "recommendation": "block",
                    "changed_files": ["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"],
                    "findings": {"critical": 2},
                }
            ],
        },
    )
    monkeypatch.setattr(
        "architec.orchestrator.answer_component_question",
        lambda root, question, component=None, llm_enabled=True: {"component": "llm-proxy:tests"},
    )
    monkeypatch.setattr(
        "architec.orchestrator.load_or_build_component_descriptors",
        lambda *args, **kwargs: {
            "llm-proxy:tests": {
                "layer_role": "test",
                "confidence": 0.8,
                "files": ["llm-proxy/tests/test_gateway_server.py"],
            },
            "llm-proxy:ops/context": {
                "layer_role": "orchestration",
                "confidence": 0.9,
                "files": ["llm-proxy/src/llm_proxy/ops/context/lifecycle.py"],
            },
        },
    )
    monkeypatch.setattr("architec.orchestrator._collect_test_candidates", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_commands", lambda *_a, **_k: [])
    monkeypatch.setattr("architec.orchestrator._build_test_command_specs", lambda *_a, **_k: [])

    out = orchestrate_analysis_modify_test(
        tmp_path,
        goal="Review architecture hotspots and fix the highest-priority issue",
        question="What should be fixed first?",
        llm_enabled=False,
        run_tests=False,
    )
    assert out["change_batches"][0]["component"] == "llm-proxy:ops/context"
