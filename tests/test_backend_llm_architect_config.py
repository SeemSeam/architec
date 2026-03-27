from __future__ import annotations

from pathlib import Path

import asyncio
import pytest
import yaml

from architec import backend_llm
from architec.backend_llm.config import (
    load_tiered_llm_config,
    resolve_gateway_timeout_sec,
    resolve_tier_candidates,
)


def _write_gateway_user_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    base_url: str = "https://primary.example",
    api_key: str = "sk-test",
    headers: dict[str, str] | None = None,
    timeout: float = 90.0,
) -> None:
    cfg_path = tmp_path / ".llmgateway-user" / "config.yaml"
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(cfg_path.parent))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "provider": {
                    "provider_type": "glm",
                    "api_style": "openai_responses",
                    "base_url": base_url,
                    "api_key": api_key,
                    "headers": dict(headers or {}),
                    "model_map": {},
                },
                "settings": {
                    "strong_model": "gpt-5.4",
                    "weak_model": "gpt-5.4",
                    "strong_reasoning_effort": "high",
                    "weak_reasoning_effort": "low",
                    "max_concurrent": 20,
                    "timeout": timeout,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_global_architect_llm_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict,
) -> None:
    cfg_path = tmp_path / ".architec-user" / "config.yaml"
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(cfg_path.parent))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")


def test_load_tiered_llm_config_reads_tier_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_gateway_user_config(tmp_path, monkeypatch, headers={"x-test": "1"})
    cfg = {
        "common_system_prompt": "sys",
        "task_prompt_prefixes": {"architect_history": "hist"},
        "failover": {
            "transport_failures_before_switch": 3,
            "parse_failures_before_switch": 1,
            "cooldown_sec": 45,
        },
        "tasks": {"architect_history": {"tier": "strong"}},
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    loaded = load_tiered_llm_config(tmp_path)

    assert loaded is not None
    assert loaded.common_system_prompt == "sys"
    assert loaded.task_prompt_prefixes["architect_history"] == "hist"
    assert "architect_folder_naming" in loaded.task_prompt_prefixes
    assert "architect_topology_review" in loaded.task_prompt_prefixes
    assert loaded.failover_policy.transport_failures_before_switch == 3
    tier, candidates = resolve_tier_candidates(
        loaded,
        task="architect_history",
        tier="weak",
    )
    assert tier == "strong"
    assert [item.provider_name for item in candidates] == ["llmgateway"]
    assert candidates[0].provider["headers"] == {"x-test": "1"}
    assert candidates[0].requested_model == "gpt-5.4"


def test_load_tiered_llm_config_resolves_env_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARCH_TEST_LLM_KEY", "sk-env-value")
    gateway_path = tmp_path / ".llmgateway-user" / "config.yaml"
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(gateway_path.parent))
    gateway_path.parent.mkdir(parents=True, exist_ok=True)
    gateway_path.write_text(
        """
version: 1
provider:
  provider_type: glm
  api_style: openai_responses
  base_url: https://primary.example
  api_key: ${ARCH_TEST_LLM_KEY}
settings:
  strong_model: gpt-5.4
  weak_model: gpt-5.4
  strong_reasoning_effort: high
  weak_reasoning_effort: low
  max_concurrent: 20
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cfg = {"tasks": {"architect_history": {"tier": "strong"}}}
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    loaded = load_tiered_llm_config(tmp_path)
    assert loaded is not None
    _, candidates = resolve_tier_candidates(
        loaded,
        task="architect_history",
        tier="strong",
    )
    assert candidates[0].provider.get("api_key") == "sk-env-value"


def test_load_tiered_llm_config_resolves_env_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARCH_TEST_PREFIX_KEY", "prefix-secret")
    gateway_path = tmp_path / ".llmgateway-user" / "config.yaml"
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(gateway_path.parent))
    gateway_path.parent.mkdir(parents=True, exist_ok=True)
    gateway_path.write_text(
        """
version: 1
provider:
  provider_type: glm
  api_style: openai_responses
  base_url: https://primary.example
  api_key: env:ARCH_TEST_PREFIX_KEY
settings:
  strong_model: gpt-5.4
  weak_model: gpt-5.4
  strong_reasoning_effort: high
  weak_reasoning_effort: low
  max_concurrent: 20
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cfg = {"tasks": {"architect_component_scoring": {"tier": "weak"}}}
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    loaded = load_tiered_llm_config(tmp_path)
    assert loaded is not None
    _, candidates = resolve_tier_candidates(
        loaded,
        task="architect_component_scoring",
        tier="weak",
    )
    assert candidates[0].provider.get("api_key") == "prefix-secret"


def test_load_tiered_llm_config_resolves_prompt_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "folder-naming-judge.md").write_text("folder naming prompt", encoding="utf-8")
    (prompts_dir / "topology-review-judge.md").write_text("topology review prompt", encoding="utf-8")
    monkeypatch.setenv("ARCHITEC_PROMPTS_DIR", str(prompts_dir))
    _write_gateway_user_config(tmp_path, monkeypatch)
    cfg = {
        "task_prompt_prefixes": {
            "architect_folder_naming": "prompt:folder-naming-judge.md",
            "architect_topology_review": "prompt:topology-review-judge.md",
        },
        "tasks": {
            "architect_folder_naming": {"tier": "weak"},
            "architect_topology_review": {"tier": "weak"},
        },
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    loaded = load_tiered_llm_config(tmp_path)

    assert loaded is not None
    assert loaded.task_prompt_prefixes["architect_folder_naming"] == "folder naming prompt"
    assert loaded.task_prompt_prefixes["architect_topology_review"] == "topology review prompt"


def test_resolve_gateway_timeout_sec_uses_gateway_timeout_floor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_gateway_user_config(tmp_path, monkeypatch, timeout=90.0)
    assert resolve_gateway_timeout_sec(20.0) == 90.0


def test_resolve_gateway_timeout_sec_keeps_larger_requested_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_gateway_user_config(tmp_path, monkeypatch, timeout=30.0)
    assert resolve_gateway_timeout_sec(45.0) == 45.0


def test_acomplete_text_applies_gateway_timeout_floor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_gateway_user_config(tmp_path, monkeypatch, timeout=90.0)
    captured: dict[str, float] = {}

    async def fake_acomplete_text_impl(project_root, **kwargs):
        del project_root
        captured["timeout_sec"] = float(kwargs["timeout_sec"])
        return {"ok": True}

    monkeypatch.setattr(backend_llm, "acomplete_text_impl", fake_acomplete_text_impl)

    out = asyncio.run(
        backend_llm.acomplete_text(
            tmp_path,
            task="architect_topology_review",
            tier="weak",
            prompt="x",
            timeout_sec=20.0,
            max_tokens=64,
            required=False,
        )
    )

    assert out == {"ok": True}
    assert captured["timeout_sec"] == 90.0
