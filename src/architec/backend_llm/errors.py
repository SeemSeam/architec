from __future__ import annotations


class BackendLLMError(RuntimeError):
    """Base backend LLM error."""


class BackendLLMUnavailableError(BackendLLMError):
    """Raised when backend LLM execution is unavailable."""


class BackendLLMResponseError(BackendLLMError):
    """Raised when backend LLM returns an invalid response payload."""


__all__ = [
    "BackendLLMError",
    "BackendLLMResponseError",
    "BackendLLMUnavailableError",
]
