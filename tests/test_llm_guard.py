from __future__ import annotations

import pytest

from architec.backend_llm import BackendLLMUnavailableError
from architec.llm_guard import ArchitectLLMUnavailableError, guard_llm_result


def test_guard_llm_result_raises_in_strict_mode() -> None:
    with pytest.raises(ArchitectLLMUnavailableError):
        guard_llm_result(
            ".",
            task="architect_history",
            runner=lambda: (_ for _ in ()).throw(
                BackendLLMUnavailableError("401 Unauthorized")
            ),
        )


def test_guard_llm_result_can_fail_open_when_requested() -> None:
    payload = guard_llm_result(
        ".",
        task="architect_history",
        fail_open=True,
        runner=lambda: (_ for _ in ()).throw(
            BackendLLMUnavailableError("401 Unauthorized")
        ),
    )
    assert isinstance(payload, dict)
    assert payload.get("status") == "unavailable"
    assert payload.get("task") == "architect_history"
