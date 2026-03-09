from __future__ import annotations

import asyncio
from types import SimpleNamespace

from architec.backend_llm_candidate_chain import run_candidate_chain


def test_run_candidate_chain_success_sets_gateway_route() -> None:
    candidate = SimpleNamespace(
        key="c1",
        provider_name="gmn",
        provider={"api_style": "openai_responses"},
        requested_model="gpt-5.3-codex",
        gateway_proxy_enabled=True,
        gateway_base_url="http://127.0.0.1:15722",
        gateway_fallback_to_direct=False,
    )
    success: list[str] = []
    failures: list[str] = []

    def _attempts(**_kwargs):
        return [("gateway", {"api_style": "openai_responses"})]

    async def _responses(**_kwargs):
        return {"ok": True, "text": "{\"ok\":true}"}

    result, err = asyncio.run(
        run_candidate_chain(
            candidates=[candidate],
            project_root=".",
            task="architect_history",
            messages=[{"role": "user", "content": "hi"}],
            effective_tier="strong",
            max_tokens=64,
            timeout_sec=1.0,
            required=True,
            policy=object(),
            normalize_model_name=lambda _p, _m: "gpt-5.3-codex",
            resolve_temperature=lambda _m, t: t,
            record_success=lambda key: success.append(key),
            record_transport_failure=lambda key, **_k: failures.append(key),
            prefers_openai_responses=lambda _p: True,
            prefers_openai_chat=lambda _p: False,
            prefers_anthropic_messages=lambda _p: False,
            provider_attempt_chain=_attempts,
            complete_openai_responses=_responses,
            complete_openai_chat=_responses,
            complete_anthropic_messages=_responses,
            complete_litellm=_responses,
        )
    )
    assert err is None
    assert result is not None
    assert result.get("provider_key") == "c1"
    assert result.get("provider_route") == "gateway"
    assert success == ["c1"]
    assert failures == []


def test_run_candidate_chain_returns_error_on_empty_model() -> None:
    candidate = SimpleNamespace(
        key="c-empty",
        provider_name="gmn",
        provider={"api_style": "openai_responses"},
        requested_model="",
        gateway_proxy_enabled=False,
        gateway_base_url="",
        gateway_fallback_to_direct=False,
    )
    failures: list[str] = []
    result, err = asyncio.run(
        run_candidate_chain(
            candidates=[candidate],
            project_root=".",
            task="architect_history",
            messages=[{"role": "user", "content": "hi"}],
            effective_tier="strong",
            max_tokens=64,
            timeout_sec=1.0,
            required=True,
            policy=object(),
            normalize_model_name=lambda _p, _m: "",
            resolve_temperature=lambda _m, t: t,
            record_success=lambda _k: None,
            record_transport_failure=lambda key, **_k: failures.append(key),
            prefers_openai_responses=lambda _p: True,
            prefers_openai_chat=lambda _p: False,
            prefers_anthropic_messages=lambda _p: False,
            provider_attempt_chain=lambda **_k: [],
            complete_openai_responses=lambda **_k: None,  # type: ignore[arg-type]
            complete_openai_chat=lambda **_k: None,  # type: ignore[arg-type]
            complete_anthropic_messages=lambda **_k: None,  # type: ignore[arg-type]
            complete_litellm=lambda **_k: None,  # type: ignore[arg-type]
        )
    )
    assert result is None
    assert err is not None
    assert "model resolution failed" in str(err)
    assert failures == ["c-empty"]
