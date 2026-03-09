from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from architec import backend_llm
from architec.backend_llm import BackendLLMConfig
from architec.backend_llm_architect_config import (
    load_architect_backend_llm_config as real_load_architect_backend_llm_config,
)
from architec.backend_llm_failover import reset_failover_state
from architec.backend_llm_parse import parse_json_object
from architec.backend_llm_transport import extract_anthropic_text


@pytest.fixture(autouse=True)
def _reset_backend_llm_state(monkeypatch) -> None:
    reset_failover_state()
    monkeypatch.setenv(
        "ARCHITEC_USER_CONFIG_DIR",
        str(Path.cwd() / ".pytest-architec-user-config-missing"),
    )
    monkeypatch.setattr(backend_llm, "load_architect_backend_llm_config", lambda _: None)


def _write_global_architect_llm_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict,
) -> None:
    cfg_path = tmp_path / ".global-architec" / "architec-llm.yaml"
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(cfg_path.parent))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")


def test_normalize_model_name_strips_openai_quality_suffix() -> None:
    provider = {"api_style": "openai_chat"}
    assert (
        backend_llm._normalize_model_name(provider, "gpt-5.3-codex high")
        == "gpt-5.3-codex"
    )
    assert (
        backend_llm._normalize_model_name(provider, "gpt-5.3-codex (high)")
        == "gpt-5.3-codex"
    )
    provider_responses = {"api_style": "openai_responses"}
    assert (
        backend_llm._normalize_model_name(provider_responses, "gpt-5.3-codex high")
        == "gpt-5.3-codex"
    )


def test_normalize_model_name_applies_model_map_before_normalize() -> None:
    provider = {
        "api_style": "openai_chat",
        "model_map": {"claude-sonnet-4-5-20250929": "gpt-5.3-codex"},
    }
    assert (
        backend_llm._normalize_model_name(provider, "claude-sonnet-4-5-20250929")
        == "gpt-5.3-codex"
    )


def test_normalize_model_name_keeps_non_openai_suffix() -> None:
    provider = {"api_style": "anthropic"}
    assert (
        backend_llm._normalize_model_name(provider, "claude-sonnet-4-5-20250929 high")
        == "claude-sonnet-4-5-20250929 high"
    )


def test_acomplete_text_uses_normalized_model(monkeypatch, tmp_path: Path) -> None:
    cfg = BackendLLMConfig(
        provider_name="right",
        provider={"api_style": "openai_chat", "base_url": "http://example.test"},
        strong_model="gpt-5.3-codex high",
        small_model="gpt-5.3-codex-medium",
        task_models={},
        common_system_prompt="",
        task_prompt_prefixes={},
    )

    seen: dict[str, str] = {}

    def fake_load(_: str | Path):
        return cfg

    async def fake_openai_completion_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        seen["model"] = model
        return '{"ok": true}'

    monkeypatch.setattr(backend_llm, "load_backend_llm_config", fake_load)
    monkeypatch.setattr(
        backend_llm,
        "_openai_chat_completion_fallback",
        fake_openai_completion_fallback,
    )

    result = asyncio.run(
        backend_llm.acomplete_text(
            tmp_path,
            task="architect_orchestrator",
            tier="strong",
            prompt="x",
            timeout_sec=1.0,
            max_tokens=64,
        )
    )
    assert result is not None
    assert result.get("ok") is True
    assert seen["model"] == "gpt-5.3-codex"
    assert result.get("model") == "gpt-5.3-codex"
    assert result.get("requested_model") == "gpt-5.3-codex high"


def test_acomplete_text_uses_openai_responses_transport(
    monkeypatch, tmp_path: Path
) -> None:
    cfg = BackendLLMConfig(
        provider_name="gmn",
        provider={"api_style": "openai_responses", "base_url": "http://example.test"},
        strong_model="gpt-5.3-codex high",
        small_model="gpt-5.3-codex-medium",
        task_models={},
        common_system_prompt="",
        task_prompt_prefixes={},
    )
    seen: dict[str, str] = {}

    def fake_load(_: str | Path):
        return cfg

    async def fake_openai_responses_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        seen["model"] = model
        return '{"ok": true, "source":"responses"}'

    monkeypatch.setattr(backend_llm, "load_backend_llm_config", fake_load)
    monkeypatch.setattr(
        backend_llm,
        "_openai_responses_completion_fallback",
        fake_openai_responses_fallback,
    )

    result = asyncio.run(
        backend_llm.acomplete_text(
            tmp_path,
            task="architect_orchestrator",
            tier="strong",
            prompt="x",
            timeout_sec=1.0,
            max_tokens=64,
        )
    )
    assert result is not None
    assert result.get("ok") is True
    assert seen["model"] == "gpt-5.3-codex"
    assert result.get("model") == "gpt-5.3-codex"


def test_acomplete_text_prefers_gateway_proxy_provider(monkeypatch, tmp_path: Path) -> None:
    cfg = BackendLLMConfig(
        provider_name="gmn",
        provider={"api_style": "openai_responses", "base_url": "https://direct.example"},
        strong_model="gpt-5.3-codex high",
        small_model="gpt-5.3-codex-medium",
        task_models={},
        common_system_prompt="",
        task_prompt_prefixes={},
        gateway_base_url="http://127.0.0.1:15722",
        gateway_proxy_enabled=True,
        gateway_fallback_to_direct=False,
    )
    seen: dict[str, str] = {}

    def fake_load(_: str | Path):
        return cfg

    async def fake_openai_responses_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        seen["base_url"] = str(provider.get("base_url", ""))
        headers = provider.get("headers", {}) if isinstance(provider, dict) else {}
        seen["cwd_header"] = str(headers.get("x-llmproxy-cwd", ""))
        return '{"ok": true, "source":"gateway"}'

    monkeypatch.setattr(backend_llm, "load_backend_llm_config", fake_load)
    monkeypatch.setattr(
        backend_llm,
        "_openai_responses_completion_fallback",
        fake_openai_responses_fallback,
    )

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
    assert seen["base_url"] == "http://127.0.0.1:15722"
    assert seen["cwd_header"] == str(tmp_path.resolve())
    assert result.get("provider_route") == "gateway"


def test_acomplete_text_gateway_fallback_to_direct(monkeypatch, tmp_path: Path) -> None:
    cfg = BackendLLMConfig(
        provider_name="gmn",
        provider={"api_style": "openai_responses", "base_url": "https://direct.example"},
        strong_model="gpt-5.3-codex high",
        small_model="gpt-5.3-codex-medium",
        task_models={},
        common_system_prompt="",
        task_prompt_prefixes={},
        gateway_base_url="http://127.0.0.1:15722",
        gateway_proxy_enabled=True,
        gateway_fallback_to_direct=True,
    )
    seen: list[str] = []

    def fake_load(_: str | Path):
        return cfg

    async def fake_openai_responses_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        base_url = str(provider.get("base_url", ""))
        seen.append(base_url)
        if base_url == "http://127.0.0.1:15722":
            raise RuntimeError("gateway down")
        return '{"ok": true, "source":"direct"}'

    monkeypatch.setattr(backend_llm, "load_backend_llm_config", fake_load)
    monkeypatch.setattr(
        backend_llm,
        "_openai_responses_completion_fallback",
        fake_openai_responses_fallback,
    )

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
    assert seen == ["http://127.0.0.1:15722", "https://direct.example"]
    assert "provider_route" not in result


def test_acomplete_text_gateway_no_fallback_hard_fails(monkeypatch, tmp_path: Path) -> None:
    cfg = BackendLLMConfig(
        provider_name="gmn",
        provider={"api_style": "openai_responses", "base_url": "https://direct.example"},
        strong_model="gpt-5.3-codex high",
        small_model="gpt-5.3-codex-medium",
        task_models={},
        common_system_prompt="",
        task_prompt_prefixes={},
        gateway_base_url="http://127.0.0.1:15722",
        gateway_proxy_enabled=True,
        gateway_fallback_to_direct=False,
    )

    def fake_load(_: str | Path):
        return cfg

    async def fake_openai_responses_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(backend_llm, "load_backend_llm_config", fake_load)
    monkeypatch.setattr(
        backend_llm,
        "_openai_responses_completion_fallback",
        fake_openai_responses_fallback,
    )

    try:
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
        assert False, "expected BackendLLMUnavailableError"
    except backend_llm.BackendLLMUnavailableError:
        pass


def test_complete_openai_responses_retries_on_transient_http_status(
    monkeypatch,
) -> None:
    import httpx

    seen_timeouts: list[float] = []

    async def fake_openai_responses_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        seen_timeouts.append(float(timeout))
        if len(seen_timeouts) == 1:
            req = httpx.Request("POST", "http://example.test/v1/responses")
            resp = httpx.Response(status_code=502, request=req)
            raise httpx.HTTPStatusError(
                "bad gateway",
                request=req,
                response=resp,
            )
        return '{"ok": true, "source": "retry"}'

    monkeypatch.setattr(
        backend_llm,
        "_openai_responses_completion_fallback",
        fake_openai_responses_fallback,
    )

    out = asyncio.run(
        backend_llm._complete_openai_responses(
            provider_cfg={"api_style": "openai_responses"},
            provider_name="gmn",
            model="gpt-5.3-codex",
            requested_model="gpt-5.3-codex",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=64,
            timeout_sec=2.0,
            temperature=0.0,
            tier="strong",
            required=True,
        )
    )
    assert out is not None
    assert out.get("ok") is True
    assert len(seen_timeouts) == 2
    assert seen_timeouts[1] > seen_timeouts[0]


def test_complete_openai_responses_does_not_retry_on_non_transient_http_status(
    monkeypatch,
) -> None:
    import httpx

    call_count = 0

    async def fake_openai_responses_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        nonlocal call_count
        call_count += 1
        req = httpx.Request("POST", "http://example.test/v1/responses")
        resp = httpx.Response(status_code=400, request=req)
        raise httpx.HTTPStatusError(
            "bad request",
            request=req,
            response=resp,
        )

    monkeypatch.setattr(
        backend_llm,
        "_openai_responses_completion_fallback",
        fake_openai_responses_fallback,
    )

    out = asyncio.run(
        backend_llm._complete_openai_responses(
            provider_cfg={"api_style": "openai_responses"},
            provider_name="gmn",
            model="gpt-5.3-codex",
            requested_model="gpt-5.3-codex",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=64,
            timeout_sec=2.0,
            temperature=0.0,
            tier="strong",
            required=False,
        )
    )
    assert out is None
    assert call_count == 1


def test_complete_openai_chat_retries_on_transient_http_status(monkeypatch) -> None:
    import httpx

    seen_timeouts: list[float] = []

    async def fake_openai_chat_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        seen_timeouts.append(float(timeout))
        if len(seen_timeouts) == 1:
            req = httpx.Request("POST", "http://example.test/v1/chat/completions")
            resp = httpx.Response(status_code=503, request=req)
            raise httpx.HTTPStatusError("service unavailable", request=req, response=resp)
        return '{"ok": true, "source": "retry"}'

    monkeypatch.setattr(
        backend_llm,
        "_openai_chat_completion_fallback",
        fake_openai_chat_fallback,
    )

    out = asyncio.run(
        backend_llm._complete_openai_chat(
            provider_cfg={"api_style": "openai_chat"},
            provider_name="right",
            model="gpt-5.3-codex",
            requested_model="gpt-5.3-codex",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=64,
            timeout_sec=2.0,
            temperature=0.0,
            tier="strong",
            required=True,
        )
    )
    assert out is not None
    assert out.get("ok") is True
    assert len(seen_timeouts) == 2
    assert seen_timeouts[1] > seen_timeouts[0]


def test_complete_anthropic_retries_on_transient_connection_error(
    monkeypatch,
) -> None:
    call_count = 0

    async def fake_anthropic_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("connection reset by peer")
        return '{"ok": true, "source": "retry"}'

    monkeypatch.setattr(
        backend_llm,
        "_anthropic_messages_completion_fallback",
        fake_anthropic_fallback,
    )

    out = asyncio.run(
        backend_llm._complete_anthropic_messages(
            provider_cfg={"api_style": "anthropic"},
            provider_name="droid",
            model="claude-sonnet-4-5-20250929",
            requested_model="claude-sonnet-4-5-20250929",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=64,
            timeout_sec=2.0,
            temperature=0.0,
            tier="strong",
            required=True,
        )
    )
    assert out is not None
    assert out.get("ok") is True
    assert call_count == 2


def test_complete_litellm_retries_on_transient_timeout(monkeypatch) -> None:
    call_count = 0

    async def fake_litellm_completion(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("request timed out")
        return '{"ok": true, "source": "retry"}'

    monkeypatch.setattr(
        backend_llm,
        "litellm_completion",
        fake_litellm_completion,
    )

    out = asyncio.run(
        backend_llm._complete_litellm(
            provider_cfg={},
            provider_name="litellm",
            model="gpt-5.3-codex",
            requested_model="gpt-5.3-codex",
            messages=[{"role": "user", "content": "hello"}],
            max_tokens=64,
            timeout_sec=2.0,
            temperature=0.0,
            tier="strong",
            required=True,
        )
    )
    assert out is not None
    assert out.get("ok") is True
    assert call_count == 2


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
    monkeypatch, tmp_path: Path
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
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        backend_llm,
        "load_architect_backend_llm_config",
        real_load_architect_backend_llm_config,
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
                "api_style": "openai_responses",
                "base_url": "https://primary.example",
                "model_map": {"gpt-5.3-codex high": "gpt-5.3-codex"},
            },
            "backup": {
                "api_style": "openai_responses",
                "base_url": "https://backup.example",
                "model_map": {"gpt-5.3-codex high": "gpt-5.3-codex"},
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
    seen: list[str] = []

    async def fake_openai_responses_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        base_url = str(provider.get("base_url", ""))
        seen.append(base_url)
        if "primary" in base_url:
            raise RuntimeError("primary down")
        return '{"ok": true, "source":"backup"}'

    monkeypatch.setattr(
        backend_llm,
        "_openai_responses_completion_fallback",
        fake_openai_responses_fallback,
    )

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


def test_acomplete_text_does_not_fallback_legacy_when_architect_yaml_exists(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        backend_llm,
        "load_architect_backend_llm_config",
        real_load_architect_backend_llm_config,
    )
    cfg_path = tmp_path / ".architec" / "architec-llm.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text("version: 1\nproviders: {}\ntiers: {}\n", encoding="utf-8")

    called = {"legacy": 0}

    def fake_load_legacy(_: str | Path):
        called["legacy"] += 1
        return BackendLLMConfig(
            provider_name="legacy",
            provider={"api_style": "openai_responses", "base_url": "https://legacy.example", "api_key": "sk-legacy"},
            strong_model="gpt-5.3-codex",
            small_model="gpt-5.3-codex-medium",
            task_models={},
            common_system_prompt="",
            task_prompt_prefixes={},
        )

    monkeypatch.setattr(backend_llm, "load_backend_llm_config", fake_load_legacy)

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
    assert called["legacy"] == 0


def test_complete_json_switches_to_backup_candidate_on_non_json_response(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARCH_BACKEND_LLM_CACHE", "0")
    monkeypatch.setattr(
        backend_llm,
        "load_architect_backend_llm_config",
        real_load_architect_backend_llm_config,
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
                "api_style": "openai_responses",
                "base_url": "https://primary.example",
                "model_map": {"gpt-5.3-codex-medium": "gpt-5.3-codex"},
            },
            "backup": {
                "api_style": "openai_responses",
                "base_url": "https://backup.example",
                "model_map": {"gpt-5.3-codex-medium": "gpt-5.3-codex"},
            },
        },
        "tiers": {
            "small": {
                "candidates": [
                    {"provider": "primary", "model": "gpt-5.3-codex-medium"},
                    {"provider": "backup", "model": "gpt-5.3-codex-medium"},
                ]
            }
        },
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)
    seen: list[str] = []

    async def fake_openai_responses_fallback(
        *,
        provider,
        model,
        messages,
        max_tokens,
        timeout,
        temperature,
    ):
        base_url = str(provider.get("base_url", ""))
        seen.append(base_url)
        if "primary" in base_url:
            return "not-json"
        return '{"ok": true, "source":"backup"}'

    monkeypatch.setattr(
        backend_llm,
        "_openai_responses_completion_fallback",
        fake_openai_responses_fallback,
    )

    out = backend_llm.complete_json(
        tmp_path,
        task="architect_history",
        tier="small",
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


def test_extract_anthropic_text_prefers_text_blocks_over_thinking() -> None:
    payload = {
        "content": [
            {"type": "thinking", "text": "draft with {broken: json"},
            {"type": "text", "text": '{"ok": true, "source": "final"}'},
        ]
    }
    assert extract_anthropic_text(payload) == '{"ok": true, "source": "final"}'


def test_extract_anthropic_text_falls_back_when_type_is_missing() -> None:
    payload = {
        "content": [
            {"text": '{"ok": true, "source": "compat"}'},
        ]
    }
    assert extract_anthropic_text(payload) == '{"ok": true, "source": "compat"}'
