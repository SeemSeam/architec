from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from architec.support.llm_guard import ArchitectLLMUnavailableError
from architec.support.llm_preflight import preflight_backend_llm


def _write_gateway_user_config(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    base_url: str = "https://api.example",
    api_key: str = "sk-test",
    api_style: str = "openai_responses",
) -> None:
    cfg_path = root / ".llmgateway-user" / "config.yaml"
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(cfg_path.parent))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "provider": {
                    "provider_type": "glm",
                    "api_style": api_style,
                    "base_url": base_url,
                    "api_key": api_key,
                    "headers": {},
                    "model_map": {},
                },
                "settings": {
                    "strong_model": "gpt-5.4",
                    "weak_model": "gpt-5.4-mini",
                    "strong_reasoning_effort": "high",
                    "weak_reasoning_effort": "low",
                    "max_concurrent": 20,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _write_global_architect_llm_yaml(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict,
) -> None:
    cfg_path = root / ".architec-user" / "config.yaml"
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(cfg_path.parent))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")


def test_preflight_backend_llm_raises_on_missing_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_gateway_user_config(tmp_path, monkeypatch, api_key="")
    cfg = {"tasks": {"architect_history": {"tier": "strong"}}}
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    with pytest.raises(ArchitectLLMUnavailableError) as exc:
        preflight_backend_llm(
            tmp_path,
            checks=[("architect_history", "strong")],
        )
    assert "missing api_key" in str(exc.value)


def test_preflight_backend_llm_passes_with_valid_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_gateway_user_config(tmp_path, monkeypatch)
    cfg = {"tasks": {"architect_history": {"tier": "strong"}}}
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    preflight_backend_llm(
        tmp_path,
        checks=[("architect_history", "strong")],
    )


def test_preflight_backend_llm_raises_on_missing_base_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_gateway_user_config(
        tmp_path,
        monkeypatch,
        base_url="",
        api_key="sk-test",
        api_style="anthropic",
    )
    cfg = {"tasks": {"architect_history": {"tier": "strong"}}}
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    with pytest.raises(ArchitectLLMUnavailableError) as exc:
        preflight_backend_llm(
            tmp_path,
            checks=[("architect_history", "strong")],
        )
    assert "missing base_url" in str(exc.value)


def test_preflight_does_not_fallback_legacy_when_architect_yaml_exists_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLMGATEWAY_USER_CONFIG_DIR", str(tmp_path / ".empty-llmgateway"))
    cfg_path = tmp_path / ".architec" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text("version: 1\nproviders: {}\ntiers: {}\n", encoding="utf-8")

    with pytest.raises(ArchitectLLMUnavailableError) as exc:
        preflight_backend_llm(
            tmp_path,
            checks=[("architect_history", "strong")],
        )
    assert "no backend LLM candidate configured" in str(exc.value)
    assert "~/.llmgateway/config.yaml" in str(exc.value)
    assert "strong_model" in str(exc.value)
    assert "weak_model" in str(exc.value)
