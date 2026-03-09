from __future__ import annotations

from types import SimpleNamespace

from architec.backend_llm_transport_text import (
    extract_anthropic_text,
    extract_openai_chat_text,
    extract_openai_responses_text,
    extract_text_from_litellm_response,
)


def test_extract_openai_chat_text_supports_list_blocks() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "alpha"},
                        {"type": "text", "text": "beta"},
                    ]
                }
            }
        ]
    }
    assert extract_openai_chat_text(payload) == "alpha\nbeta"


def test_extract_openai_responses_text_supports_output_text_array() -> None:
    payload = {"output_text": ["line-1", "line-2"]}
    assert extract_openai_responses_text(payload) == "line-1\nline-2"


def test_extract_anthropic_text_prefers_text_type_blocks() -> None:
    payload = {
        "content": [
            {"type": "thinking", "text": "draft"},
            {"type": "text", "text": '{"ok": true}'},
        ]
    }
    assert extract_anthropic_text(payload) == '{"ok": true}'


def test_extract_text_from_litellm_response_reads_choices_message_content() -> None:
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="final-answer"))]
    )
    assert extract_text_from_litellm_response(response) == "final-answer"
