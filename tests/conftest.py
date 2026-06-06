from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def default_architec_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHITEC_LANG", "en")
