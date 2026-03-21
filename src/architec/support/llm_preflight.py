from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from architec.backend_llm.config import (
    LLMCandidate,
    load_tiered_llm_config,
    resolve_tier_candidates,
)
from architec.support.llm_guard import ArchitectLLMUnavailableError
from architec.integration.resource_paths import resolve_architect_llm_config_file


@dataclass(frozen=True)
class _CandidateView:
    provider_name: str
    task: str
    tier: str
    model: str
    provider: dict


def _candidate_view(
    candidate: LLMCandidate,
    *,
    task: str,
    tier: str,
) -> _CandidateView:
    return _CandidateView(
        provider_name=candidate.provider_name,
        task=task,
        tier=tier,
        model=candidate.requested_model,
        provider=dict(candidate.provider),
    )


def _tiered_candidate_views(
    tiered_cfg: object,
    *,
    task: str,
    tier: str,
) -> list[_CandidateView]:
    if tiered_cfg is None:
        return []
    effective_tier, candidates = resolve_tier_candidates(
        tiered_cfg,
        task=task,
        tier=tier,
    )
    out: list[_CandidateView] = []
    for candidate in candidates:
        if isinstance(candidate, LLMCandidate):
            out.append(_candidate_view(candidate, task=task, tier=effective_tier))
    return out


def _collect_candidates(
    project_root: Path,
    *,
    task: str,
    tier: str,
) -> list[_CandidateView]:
    cfg_path = resolve_architect_llm_config_file(project_root)
    tiered_cfg = load_tiered_llm_config(project_root)
    if cfg_path.exists():
        return _tiered_candidate_views(tiered_cfg, task=task, tier=tier)
    if tiered_cfg is not None:
        out = _tiered_candidate_views(tiered_cfg, task=task, tier=tier)
        if out:
            return out
    return []


def _candidate_problems(candidate: _CandidateView) -> list[str]:
    provider = candidate.provider
    api_style = str(provider.get("api_style", "") or "").strip().lower()
    base_url = str(provider.get("base_url", "") or "").strip()
    api_key = str(provider.get("api_key", "") or "").strip()
    label = (
        f"task={candidate.task} tier={candidate.tier} "
        f"provider={candidate.provider_name} model={candidate.model}"
    )
    problems: list[str] = []
    if not api_key:
        problems.append(f"- {label}: missing api_key")
    if api_style and not base_url:
        problems.append(f"- {label}: missing base_url for api_style={api_style}")
    return problems


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
            problems.extend(_candidate_problems(candidate))

    if problems:
        raise ArchitectLLMUnavailableError(
            "Architec LLM preflight failed:\n"
            + "\n".join(problems)
            + "\nHint: configure ~/.llmgateway/config.yaml and ~/.architec/config.yaml, or provide project overrides in .architec/config.yaml."
        )
