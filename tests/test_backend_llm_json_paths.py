from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from llmgateway.spec import CallResult
from llmgateway.transport_text import extract_anthropic_text

from architec import backend_llm
from architec.backend_llm.config import (
    load_tiered_llm_config as real_load_tiered_llm_config,
)
from architec.backend_llm.parse import parse_json_object

from tests.backend_llm_test_support import (
    _reset_backend_llm_state,
    _write_global_architect_llm_yaml,
)


def test_complete_json_includes_requested_model_marker(monkeypatch) -> None:
    monkeypatch.setenv("ARCH_BACKEND_LLM_CACHE", "0")

    def fake_complete_text(*args, **kwargs):
        return {
            "ok": True,
            "text": '{"hello": "world"}',
            "model": "gpt-5.3-codex",
            "requested_model": "gpt-5.3-codex high",
            "tier": "strong",
            "provider": "right",
            "provider_route": "gateway",
        }

    monkeypatch.setattr(backend_llm, "complete_text", fake_complete_text)
    obj = backend_llm.complete_json(
        Path("."),
        task="architect_orchestrator",
        tier="strong",
        prompt="x",
    )
    assert obj is not None
    assert obj["_llm_model"] == "gpt-5.3-codex"
    assert obj["_llm_model_requested"] == "gpt-5.3-codex high"
    assert obj["_llm_provider_route"] == "gateway"


def test_complete_json_required_raises_when_backend_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("ARCH_BACKEND_LLM_CACHE", "0")

    def fake_complete_text(*args, **kwargs):
        return None

    monkeypatch.setattr(backend_llm, "complete_text", fake_complete_text)
    try:
        backend_llm.complete_json(
            Path("."),
            task="architect_orchestrator",
            tier="strong",
            prompt="x",
            required=True,
        )
        assert False, "expected BackendLLMUnavailableError"
    except backend_llm.BackendLLMUnavailableError:
        pass


def test_complete_json_non_required_keeps_legacy_none(monkeypatch) -> None:
    monkeypatch.setenv("ARCH_BACKEND_LLM_CACHE", "0")

    def fake_complete_text(*args, **kwargs):
        return None

    monkeypatch.setattr(backend_llm, "complete_text", fake_complete_text)
    out = backend_llm.complete_json(
        Path("."),
        task="architect_orchestrator",
        tier="strong",
        prompt="x",
        required=False,
    )
    assert out is None


def test_complete_json_reuses_cache_for_same_prompt(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ARCH_BACKEND_LLM_CACHE", "1")
    calls = {"count": 0}

    def fake_complete_text(*args, **kwargs):
        calls["count"] += 1
        return {
            "ok": True,
            "text": '{"cached": true}',
            "model": "gpt-5.3-codex",
            "requested_model": "gpt-5.3-codex high",
            "tier": "strong",
            "provider": "right",
            "provider_route": "gateway",
        }

    monkeypatch.setattr(backend_llm, "complete_text", fake_complete_text)

    first = backend_llm.complete_json(
        tmp_path,
        task="architect_orchestrator",
        tier="strong",
        prompt="same-prompt",
    )
    second = backend_llm.complete_json(
        tmp_path,
        task="architect_orchestrator",
        tier="strong",
        prompt="same-prompt",
    )

    assert first is not None
    assert second is not None
    assert first["cached"] is True
    assert second["cached"] is True
    assert calls["count"] == 1


def test_complete_text_switches_to_backup_candidate_on_transport_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        backend_llm,
        "load_tiered_llm_config",
        real_load_tiered_llm_config,
    )
    cfg = {
        "common_system_prompt": "",
        "task_prompt_prefixes": {},
        "failover": {
            "transport_failures_before_switch": 1,
            "parse_failures_before_switch": 1,
            "cooldown_sec": 60,
        },
        "providers": {
            "primary": {
                "api_style": "responses",
                "base_url": "https://primary.example",
                "model_map": {"strong-model high": "strong-model"},
            },
            "backup": {
                "api_style": "responses",
                "base_url": "https://backup.example",
                "model_map": {"strong-model high": "strong-model"},
            },
        },
        "tiers": {
            "strong": {
                "candidates": [
                    {"provider": "primary", "model": "strong-model high"},
                    {"provider": "backup", "model": "strong-model high"},
                ]
            }
        },
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)
    seen: list[str] = []

    async def fake_generate(self, request):
        base_url = self.runtime.provider.base_url
        seen.append(base_url)
        if "primary" in base_url:
            raise RuntimeError("primary down")
        return CallResult(
            task=request.task,
            text='{"ok": true, "source":"backup"}',
            requested_model="strong-model high",
            normalized_model="strong-model",
            reasoning_effort="high",
            temperature=0.0,
            max_tokens=int(request.max_tokens or 0),
        )

    monkeypatch.setattr("llmgateway.service.LLMService.generate", fake_generate)

    result = asyncio.run(
        backend_llm.acomplete_text(
            tmp_path,
            task="architect_orchestrator",
            tier="strong",
            prompt="x",
            timeout_sec=1.0,
            max_tokens=64,
            required=True,
        )
    )

    assert result is not None
    assert result.get("ok") is True
    assert seen == ["https://primary.example", "https://backup.example"]
    assert result.get("provider") == "backup:direct"


def test_acomplete_text_raises_when_architect_yaml_exists_invalid(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(tmp_path / ".empty-llmgateway"))
    monkeypatch.setattr(
        backend_llm,
        "load_tiered_llm_config",
        real_load_tiered_llm_config,
    )
    cfg_path = tmp_path / ".architec" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text("version: 1\nproviders: {}\ntiers: {}\n", encoding="utf-8")

    with pytest.raises(backend_llm.BackendLLMUnavailableError):
        asyncio.run(
            backend_llm.acomplete_text(
                tmp_path,
                task="architect_orchestrator",
                tier="strong",
                prompt="x",
                timeout_sec=1.0,
                max_tokens=64,
                required=True,
            )
        )


def test_complete_json_switches_to_backup_candidate_on_non_json_response(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ARCH_BACKEND_LLM_CACHE", "0")
    monkeypatch.setattr(
        backend_llm,
        "load_tiered_llm_config",
        real_load_tiered_llm_config,
    )
    cfg = {
        "common_system_prompt": "",
        "task_prompt_prefixes": {},
        "failover": {
            "transport_failures_before_switch": 2,
            "parse_failures_before_switch": 1,
            "cooldown_sec": 60,
        },
        "providers": {
            "primary": {
                "api_style": "responses",
                "base_url": "https://primary.example",
                "model_map": {"small-model": "small-model"},
            },
            "backup": {
                "api_style": "responses",
                "base_url": "https://backup.example",
                "model_map": {"small-model": "small-model"},
            },
        },
        "tiers": {
            "weak": {
                "candidates": [
                    {"provider": "primary", "model": "small-model"},
                    {"provider": "backup", "model": "small-model"},
                ]
            }
        },
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)
    seen: list[str] = []

    async def fake_generate(self, request):
        base_url = self.runtime.provider.base_url
        seen.append(base_url)
        if "primary" in base_url:
            return CallResult(
                task=request.task,
                text="not-json",
                requested_model="small-model",
                normalized_model="small-model",
                reasoning_effort="",
                temperature=0.0,
                max_tokens=int(request.max_tokens or 0),
            )
        return CallResult(
            task=request.task,
            text='{"ok": true, "source":"backup"}',
            requested_model="small-model",
            normalized_model="small-model",
            reasoning_effort="",
            temperature=0.0,
            max_tokens=int(request.max_tokens or 0),
        )

    monkeypatch.setattr("llmgateway.service.LLMService.generate", fake_generate)

    out = backend_llm.complete_json(
        tmp_path,
        task="architect_component_scoring",
        tier="weak",
        prompt="x",
        required=True,
    )
    assert out is not None
    assert out["ok"] is True
    assert seen == ["https://primary.example", "https://backup.example"]
    assert out["_llm_provider"] == "backup:direct"


def test_parse_json_object_accepts_markdown_fenced_payload() -> None:
    payload = """analysis
```json
{"ok": true, "value": 7}
```
"""
    out = parse_json_object(payload)
    assert out == {"ok": True, "value": 7}


def test_parse_json_object_accepts_trailing_commas() -> None:
    payload = '{"ok": true, "items": [1,2,],}'
    out = parse_json_object(payload)
    assert out == {"ok": True, "items": [1, 2]}


def test_parse_json_object_accepts_python_dict_style() -> None:
    payload = "{'ok': True, 'msg': 'x'}"
    out = parse_json_object(payload)
    assert out == {"ok": True, "msg": "x"}


def test_parse_json_object_handles_escaped_quotes_inside_json() -> None:
    payload = 'prefix {"ok": true, "msg": "say \\"hi\\""} suffix'
    out = parse_json_object(payload)
    assert out == {"ok": True, "msg": 'say "hi"'}


def test_parse_json_object_prefers_first_balanced_object_candidate() -> None:
    payload = 'noise {"ok": true} trailing {"later": false}'
    out = parse_json_object(payload)
    assert out == {"ok": True}


def test_extract_anthropic_text_prefers_text_blocks_over_thinking() -> None:
    payload = {
        "content": [
            {"type": "thinking", "text": "draft with {broken: json"},
            {"type": "text", "text": '{"ok": true, "source": "final"}'},
        ]
    }
    assert extract_anthropic_text(payload) == '{"ok": true, "source": "final"}'


def test_extract_anthropic_text_falls_back_when_type_is_missing() -> None:
    payload = {"content": [{"text": '{"ok": true, "source": "compat"}'}]}
    assert extract_anthropic_text(payload) == '{"ok": true, "source": "compat"}'
