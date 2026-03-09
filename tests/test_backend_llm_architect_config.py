from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from architec.backend_llm_architect_config import (
    load_architect_backend_llm_config,
    resolve_architect_candidates,
)


def _write_global_architect_llm_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict,
) -> None:
    cfg_path = tmp_path / ".global-architec" / "architec-llm.yaml"
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(cfg_path.parent))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")


def test_load_architect_backend_llm_config_reads_tier_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = {
        "common_system_prompt": "sys",
        "task_prompt_prefixes": {"architect_history": "hist"},
        "failover": {
            "transport_failures_before_switch": 3,
            "parse_failures_before_switch": 1,
            "cooldown_sec": 45,
        },
        "providers": {
            "primary": {
                "api_style": "openai_responses",
                "base_url": "https://primary.example",
                "headers": {"x-test": "1"},
            },
            "backup": {
                "api_style": "anthropic",
                "base_url": "https://backup.example",
            },
        },
        "tiers": {
            "strong": {
                "candidates": [
                    {"provider": "primary", "model": "gpt-5.3-codex high"},
                    {"provider": "backup", "model": "gpt-5.3-codex high"},
                ]
            }
        },
        "tasks": {"architect_history": {"tier": "strong"}},
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    loaded = load_architect_backend_llm_config(tmp_path)

    assert loaded is not None
    assert loaded.common_system_prompt == "sys"
    assert loaded.task_prompt_prefixes == {"architect_history": "hist"}
    assert loaded.failover_policy.transport_failures_before_switch == 3
    tier, candidates = resolve_architect_candidates(
        loaded,
        task="architect_history",
        tier="small",
    )
    assert tier == "strong"
    assert [item.provider_name for item in candidates] == ["primary", "backup"]
    assert candidates[0].provider["headers"] == {"x-test": "1"}


def test_load_architect_backend_llm_config_resolves_env_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARCH_TEST_LLM_KEY", "sk-env-value")
    cfg = {
        "providers": {
            "primary": {
                "api_style": "openai_responses",
                "base_url": "https://primary.example",
                "api_key": "${ARCH_TEST_LLM_KEY}",
            },
            "backup": {
                "api_style": "anthropic",
                "base_url": "https://backup.example",
                "api_key": "${ARCH_TEST_MISSING_KEY:-fallback-key}",
            },
        },
        "tiers": {
            "strong": {
                "candidates": [
                    {"provider": "primary", "model": "gpt-5.3-codex high"},
                    {"provider": "backup", "model": "gpt-5.3-codex high"},
                ]
            }
        },
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    loaded = load_architect_backend_llm_config(tmp_path)
    assert loaded is not None
    _, candidates = resolve_architect_candidates(
        loaded,
        task="architect_history",
        tier="strong",
    )
    assert candidates[0].provider.get("api_key") == "sk-env-value"
    assert candidates[1].provider.get("api_key") == "fallback-key"


def test_load_architect_backend_llm_config_resolves_env_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARCH_TEST_PREFIX_KEY", "prefix-secret")
    cfg = {
        "providers": {
            "primary": {
                "api_style": "openai_responses",
                "base_url": "https://primary.example",
                "api_key": "env:ARCH_TEST_PREFIX_KEY",
            }
        },
        "tiers": {
            "small": {
                "candidates": [
                    {"provider": "primary", "model": "gpt-5.3-codex-medium"},
                ]
            }
        },
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    loaded = load_architect_backend_llm_config(tmp_path)
    assert loaded is not None
    _, candidates = resolve_architect_candidates(
        loaded,
        task="architect_history",
        tier="small",
    )
    assert candidates[0].provider.get("api_key") == "prefix-secret"
