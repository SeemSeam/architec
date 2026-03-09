from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .backend_llm_architect_config import (
    ArchitectLLMCandidate,
    load_architect_backend_llm_config,
    resolve_architect_candidates,
)
from .backend_llm_config import choose_model, load_backend_llm_config
from .llm_guard import ArchitectLLMUnavailableError
from .resource_paths import resolve_architect_llm_config_file


@dataclass(frozen=True)
class _CandidateView:
    provider_name: str
    task: str
    tier: str
    model: str
    provider: dict


def _collect_candidates(
    project_root: Path,
    *,
    task: str,
    tier: str,
) -> list[_CandidateView]:
    cfg_path = resolve_architect_llm_config_file(project_root)
    architect_cfg = load_architect_backend_llm_config(project_root)
    if cfg_path.exists():
        if architect_cfg is None:
            return []
        effective_tier, candidates = resolve_architect_candidates(
            architect_cfg,
            task=task,
            tier=tier,
        )
        out: list[_CandidateView] = []
        for candidate in candidates:
            if not isinstance(candidate, ArchitectLLMCandidate):
                continue
            out.append(
                _CandidateView(
                    provider_name=candidate.provider_name,
                    task=task,
                    tier=effective_tier,
                    model=candidate.requested_model,
                    provider=dict(candidate.provider),
                )
            )
        return out
    if architect_cfg is not None:
        effective_tier, candidates = resolve_architect_candidates(
            architect_cfg,
            task=task,
            tier=tier,
        )
        out: list[_CandidateView] = []
        for candidate in candidates:
            if not isinstance(candidate, ArchitectLLMCandidate):
                continue
            out.append(
                _CandidateView(
                    provider_name=candidate.provider_name,
                    task=task,
                    tier=effective_tier,
                    model=candidate.requested_model,
                    provider=dict(candidate.provider),
                )
            )
        if out:
            return out

    legacy_cfg = load_backend_llm_config(project_root)
    if legacy_cfg is None:
        return []
    model = choose_model(legacy_cfg, task=task, tier=tier)
    return [
        _CandidateView(
            provider_name=legacy_cfg.provider_name,
            task=task,
            tier=tier,
            model=model,
            provider=dict(legacy_cfg.provider),
        )
    ]


def preflight_backend_llm(
    project_root: str | Path,
    *,
    checks: list[tuple[str, str]],
) -> None:
    """Validate backend LLM config before running architect commands.

    Raises ArchitectLLMUnavailableError when required provider fields are missing.
    """
    root = Path(project_root).resolve()
    problems: list[str] = []
    seen = set()

    for task, tier in checks:
        key = (str(task or "").strip(), str(tier or "").strip())
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        candidates = _collect_candidates(root, task=key[0], tier=key[1])
        if not candidates:
            problems.append(
                f"- task={key[0]} tier={key[1]}: no backend LLM candidate configured"
            )
            continue

        for candidate in candidates:
            provider = candidate.provider
            api_style = str(provider.get("api_style", "") or "").strip().lower()
            base_url = str(provider.get("base_url", "") or "").strip()
            api_key = str(provider.get("api_key", "") or "").strip()
            label = (
                f"task={candidate.task} tier={candidate.tier} "
                f"provider={candidate.provider_name} model={candidate.model}"
            )
            if not api_key:
                problems.append(f"- {label}: missing api_key")
            if api_style in {"openai_chat", "openai_responses", "anthropic"} and not base_url:
                problems.append(f"- {label}: missing base_url for api_style={api_style}")

    if problems:
        raise ArchitectLLMUnavailableError(
            "Architect backend LLM preflight failed:\n"
            + "\n".join(problems)
            + "\nHint: run ./install.sh to write global LLM config, or provide api_key/base_url in ~/.architec/architec-llm.yaml."
        )
