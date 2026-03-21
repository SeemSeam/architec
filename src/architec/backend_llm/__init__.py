from __future__ import annotations

import logging
from pathlib import Path

from .cache import load_cached_result, save_cached_result
from .config import (
    LLMCandidate,
    load_tiered_llm_config,
    normalize_model_name,
    resolve_tier_candidates,
)
from .errors import (
    BackendLLMError,
    BackendLLMResponseError,
    BackendLLMUnavailableError,
)
from .failover import (
    FailoverPolicy,
    record_parse_failure,
    record_success,
    record_transport_failure,
)
from .flow import (
    acomplete_text_impl,
    build_messages_for_candidate,
    complete_json_impl,
    complete_text_impl,
    default_failover_policy,
    process_json_attempt,
    process_json_attempt_with_logger,
    provider_attempt_chain,
    resolve_provider_hint_context,
    resolve_runtime_context_strict,
)
from .gateway import (
    build_runtime_spec,
    run_candidate_chain_via_gateway,
)
from architec.integration.resource_paths import resolve_architect_llm_config_file

logger = logging.getLogger("architec.backend_llm")


def _resolve_runtime_context(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
) -> tuple[str, list[LLMCandidate], str, dict[str, str], FailoverPolicy]:
    return resolve_runtime_context_strict(
        project_root,
        task=task,
        tier=tier,
        tiered_cfg_loader=load_tiered_llm_config,
        resolve_candidates=resolve_tier_candidates,
    )


async def acomplete_text(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float = 20.0,
    max_tokens: int = 700,
    required: bool = False,
) -> dict[str, object] | None:
    return await acomplete_text_impl(
        project_root,
        task=task,
        tier=tier,
        prompt=prompt,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        required=required,
        resolve_runtime_context_fn=_resolve_runtime_context,
        missing_config_message=(
            "llm config missing under ~/.llmgateway/config.yaml and ~/.architec/config.yaml, "
            f"optional project override {resolve_architect_llm_config_file(project_root)}"
        ),
        build_messages_fn=build_messages_for_candidate,
        run_candidate_chain_fn=run_candidate_chain_via_gateway,
        record_success_fn=record_success,
        record_transport_failure_fn=record_transport_failure,
        provider_attempt_chain_fn=provider_attempt_chain,
    )


def complete_text(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float = 20.0,
    max_tokens: int = 700,
    required: bool = False,
) -> dict[str, object] | None:
    return complete_text_impl(
        acomplete_text_fn=acomplete_text,
        project_root=project_root,
        task=task,
        tier=tier,
        prompt=prompt,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        required=required,
    )


def _processed_json_attempt(
    *,
    raw: dict[str, object] | None,
    task: str,
    tier: str,
    required: bool,
    policy: FailoverPolicy,
) -> dict[str, object]:
    return process_json_attempt_with_logger(
        raw=raw,
        task=task,
        tier=tier,
        required=required,
        policy=policy,
        process_json_attempt_fn=process_json_attempt,
        record_parse_failure_fn=record_parse_failure,
        logger=logger,
    )


def complete_json(
    project_root: str | Path,
    *,
    task: str,
    tier: str,
    prompt: str,
    timeout_sec: float = 20.0,
    max_tokens: int = 700,
    required: bool = True,
) -> dict[str, object] | None:
    return complete_json_impl(
        project_root,
        task=task,
        tier=tier,
        prompt=prompt,
        timeout_sec=timeout_sec,
        max_tokens=max_tokens,
        required=required,
        resolve_provider_hint_context_fn=resolve_provider_hint_context,
        resolve_runtime_context_fn=_resolve_runtime_context,
        normalize_model_name_fn=normalize_model_name,
        default_failover_policy_fn=default_failover_policy,
        load_cached_result_fn=load_cached_result,
        save_cached_result_fn=save_cached_result,
        complete_text_fn=complete_text,
        process_json_attempt_fn=_processed_json_attempt,
    )


__all__ = [
    "LLMCandidate",
    "BackendLLMError",
    "BackendLLMResponseError",
    "BackendLLMUnavailableError",
    "FailoverPolicy",
    "acomplete_text",
    "build_runtime_spec",
    "complete_json",
    "complete_text",
    "load_tiered_llm_config",
]
