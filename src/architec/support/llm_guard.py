from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from architec.backend_llm import BackendLLMError

logger = logging.getLogger("architec.llm_guard")


class ArchitectLLMUnavailableError(RuntimeError):
    """Raised when architect workflow requires LLM but backend is unavailable."""


def llm_unavailable_payload(*, task: str, error: Exception | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "unavailable",
        "task": task,
    }
    if error is not None:
        payload["error_type"] = type(error).__name__
        payload["error"] = str(error)
    return payload


def _build_error_message(
    *,
    project_root: str | Path,
    task: str,
    error: Exception,
) -> str:
    root = Path(project_root).resolve()
    message = (
        f"Architect backend LLM unavailable (task={task}, root={root}, "
        f"error_type={type(error).__name__}): {error}"
    )
    text = str(error)
    if "401" in text or "Unauthorized" in text:
        message += (
            " | Check backend API keys/config. "
            "Expected env vars: architec_llm_main_api_key / architec_llm_main_url."
        )
    return message


def guard_llm_result(
    project_root: str | Path,
    *,
    task: str,
    runner: callable,
    fail_open: bool = False,
    require_result: bool = True,
) -> dict[str, Any] | None:
    try:
        result = runner()
        if result is None and require_result:
            raise ArchitectLLMUnavailableError(
                f"Architect backend LLM returned empty result for task={task}"
            )
        return result
    except ArchitectLLMUnavailableError as exc:
        if fail_open:
            return llm_unavailable_payload(task=task, error=exc)
        raise
    except BackendLLMError as exc:
        message = _build_error_message(project_root=project_root, task=task, error=exc)
        logger.error(
            "llm enhancement unavailable task=%s root=%s err_type=%s err=%r",
            task,
            Path(project_root).resolve(),
            type(exc).__name__,
            exc,
        )
        if fail_open:
            return llm_unavailable_payload(task=task, error=exc)
        raise ArchitectLLMUnavailableError(message) from exc
    except Exception as exc:
        message = _build_error_message(project_root=project_root, task=task, error=exc)
        logger.exception(
            "llm enhancement crashed task=%s root=%s err_type=%s",
            task,
            Path(project_root).resolve(),
            type(exc).__name__,
        )
        if fail_open:
            return llm_unavailable_payload(task=task, error=exc)
        raise ArchitectLLMUnavailableError(message) from exc
