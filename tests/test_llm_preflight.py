from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from architec.llm_guard import ArchitectLLMUnavailableError
from architec.llm_preflight import preflight_backend_llm


def _write_global_architect_llm_yaml(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict,
) -> None:
    cfg_path = root / ".global-architec" / "architec-llm.yaml"
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(cfg_path.parent))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")


def test_preflight_backend_llm_raises_on_missing_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = {
        "providers": {
            "primary": {
                "api_style": "openai_responses",
                "base_url": "https://api.example",
                "api_key": "",
            }
        },
        "tiers": {
            "strong": {
                "candidates": [
                    {"provider": "primary", "model": "gpt-5.3-codex high"},
                ]
            }
        },
    }
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
    cfg = {
        "providers": {
            "primary": {
                "api_style": "openai_responses",
                "base_url": "https://api.example",
                "api_key": "sk-test",
            }
        },
        "tiers": {
            "strong": {
                "candidates": [
                    {"provider": "primary", "model": "gpt-5.3-codex high"},
                ]
            }
        },
    }
    _write_global_architect_llm_yaml(tmp_path, monkeypatch, cfg)

    preflight_backend_llm(
        tmp_path,
        checks=[("architect_history", "strong")],
    )


def test_preflight_does_not_fallback_legacy_when_architect_yaml_exists_invalid(
    tmp_path: Path,
) -> None:
    cfg_path = tmp_path / ".architec" / "architec-llm.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text("version: 1\nproviders: {}\ntiers: {}\n", encoding="utf-8")

    with pytest.raises(ArchitectLLMUnavailableError) as exc:
        preflight_backend_llm(
            tmp_path,
            checks=[("architect_history", "strong")],
        )
    assert "no backend LLM candidate configured" in str(exc.value)
