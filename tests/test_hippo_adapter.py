from __future__ import annotations

from pathlib import Path

from architec.integration.hippo_adapter import HippoSnapshot


def _snapshot(tmp_path: Path) -> HippoSnapshot:
    return HippoSnapshot(
        project_root=tmp_path,
        metrics={},
        index={},
        signatures={},
        structure_prompt="",
    )


def test_component_for_path_keeps_project_specific_mapping(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    out = snapshot.component_for_path(
        "llm-proxy/src/llm_proxy/ops/context/lifecycle.py"
    )
    assert out == "llm-proxy:ops/context"


def test_component_for_path_uses_generic_src_mapping(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    out = snapshot.component_for_path("service/src/payments/engine.py")
    assert out == "service:payments"


def test_component_for_path_uses_generic_tests_mapping(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    out = snapshot.component_for_path("service/tests/test_payments.py")
    assert out == "service:tests"


def test_component_for_path_strips_file_suffix_for_project_packages(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    out1 = snapshot.component_for_path("hippos/src/hippos/cli_commands_pipeline.py")
    out2 = snapshot.component_for_path("llm-proxy/src/llm_proxy/project_router.py")
    assert out1 == "hippos:cli_commands_pipeline"
    assert out2 == "llm-proxy:project_router"


def test_snapshot_prefers_manifest_for_source_and_test_paths(tmp_path: Path) -> None:
    snapshot = HippoSnapshot(
        project_root=tmp_path,
        metrics={},
        index={},
        signatures={},
        structure_prompt="",
        file_manifest={
            "files": {
                "src/service/engine.py": {
                    "kind": "source",
                    "include_in_architecture": True,
                    "include_in_test_support": False,
                },
                "tests/test_engine.py": {
                    "kind": "test",
                    "include_in_architecture": False,
                    "include_in_test_support": True,
                },
            }
        },
    )

    assert snapshot.first_party_paths() == ["src/service/engine.py"]
    assert snapshot.test_support_paths() == ["tests/test_engine.py"]
    assert snapshot.file_kind("tests/test_engine.py") == "test"
