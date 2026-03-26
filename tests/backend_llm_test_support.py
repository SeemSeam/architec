from __future__ import annotations

from pathlib import Path

import pytest

from architec import backend_llm
from architec.backend_llm.failover import reset_failover_state


@pytest.fixture(autouse=True)
def _reset_backend_llm_state(monkeypatch) -> None:
    reset_failover_state()
    monkeypatch.setenv(
        "ARCHITEC_USER_CONFIG_DIR",
        str(Path.cwd() / ".pytest-architec-user-config-missing"),
    )
    monkeypatch.setattr(backend_llm, "load_tiered_llm_config", lambda _: None)


def _write_global_architect_llm_yaml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cfg: dict,
) -> None:
    cfg_path = tmp_path / ".architec-user" / "config.yaml"
    monkeypatch.setenv("ARCHITEC_USER_CONFIG_DIR", str(cfg_path.parent))
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
