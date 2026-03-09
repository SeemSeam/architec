from __future__ import annotations


class BackendLLMError(Exception):
    """Base error for backend LLM hard-fail mode."""


class BackendLLMUnavailableError(BackendLLMError):
    """Backend LLM is unavailable due to config/transport/runtime failure."""


class BackendLLMResponseError(BackendLLMError):
    """Backend LLM returned an invalid/unparseable response payload."""


__all__ = [
    "BackendLLMError",
    "BackendLLMResponseError",
    "BackendLLMUnavailableError",
]
