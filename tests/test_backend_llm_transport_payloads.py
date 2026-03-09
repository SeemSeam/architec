from __future__ import annotations

from architec.backend_llm_transport_payloads import (
    build_anthropic_headers,
    build_openai_headers,
    build_openai_responses_payload,
    build_openai_responses_url,
)


def test_build_openai_responses_url_handles_common_base_styles() -> None:
    assert build_openai_responses_url({"base_url": "https://api.example"}) == "https://api.example/v1/responses"
    assert build_openai_responses_url({"base_url": "https://api.example/v1"}) == "https://api.example/v1/responses"
    assert (
        build_openai_responses_url({"base_url": "https://api.example/v1/responses"})
        == "https://api.example/v1/responses"
    )


def test_build_openai_headers_keeps_custom_headers_and_filters_reserved() -> None:
    headers = build_openai_headers(
        {
            "api_key": "sk-test",
            "headers": {
                "x-trace-id": "abc",
                "authorization": "bad",
                "content-type": "text/plain",
            },
        }
    )
    assert headers["authorization"] == "Bearer sk-test"
    assert headers["content-type"] == "application/json"
    assert headers["x-trace-id"] == "abc"


def test_build_openai_responses_payload_moves_system_to_instructions() -> None:
    payload = build_openai_responses_payload(
        model="gpt-5.3-codex",
        messages=[
            {"role": "system", "content": "rule-1"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "world"},
        ],
        max_tokens=128,
        temperature=0.1,
    )
    assert payload["model"] == "gpt-5.3-codex"
    assert payload["instructions"] == "rule-1"
    assert len(payload["input"]) == 2


def test_build_anthropic_headers_sets_defaults() -> None:
    headers = build_anthropic_headers({"api_key": "sk-a"})
    assert headers["content-type"] == "application/json"
    assert headers["x-api-key"] == "sk-a"
    assert headers["authorization"] == "Bearer sk-a"
    assert headers["anthropic-version"] == "2023-06-01"
