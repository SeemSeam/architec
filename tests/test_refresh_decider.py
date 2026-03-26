from __future__ import annotations

from pathlib import Path

from architec.support import refresh_decider


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_decider_mode_never_disables_all_refresh(tmp_path: Path) -> None:
    out = refresh_decider.decide_refresh_actions(
        tmp_path,
        refresh_mode="never",
        phase="baseline",
        hippo_needed=True,
        metrics_needed=True,
    )
    assert out["hippo_refresh"] is False
    assert out["metrics_refresh"] is False
    assert out["force_full_refresh"] is False


def test_decider_periodic_full_refresh(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ARCH_FULL_REFRESH_INTERVAL", "2")
    monkeypatch.setattr(
        refresh_decider,
        "_collect_git_change_signals",
        lambda root: {
            "changed_total": 0,
            "structural_total": 0,
            "structural_ratio": 0.0,
            "trigger": False,
            "thresholds": {},
        },
    )

    first = refresh_decider.decide_refresh_actions(
        tmp_path,
        refresh_mode="auto",
        phase="baseline",
        hippo_needed=False,
        metrics_needed=False,
    )
    second = refresh_decider.decide_refresh_actions(
        tmp_path,
        refresh_mode="auto",
        phase="baseline",
        hippo_needed=False,
        metrics_needed=False,
    )

    assert first["force_full_refresh"] is False
    assert second["force_full_refresh"] is True
    assert "periodic full refresh" in second["reasons"]


def test_decider_forces_full_refresh_when_contract_changes(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(refresh_decider, "package_root", lambda: tmp_path / "architec")
    monkeypatch.setenv("ARCH_FULL_REFRESH_INTERVAL", "99")
    monkeypatch.setattr(
        refresh_decider,
        "_collect_git_change_signals",
        lambda root: {
            "changed_total": 0,
            "structural_total": 0,
            "structural_ratio": 0.0,
            "trigger": False,
            "thresholds": {},
        },
    )

    rubric = tmp_path / "architec/config/rubric.json"
    _write(rubric, '{"v":1}')

    first = refresh_decider.decide_refresh_actions(
        tmp_path,
        refresh_mode="auto",
        phase="baseline",
        hippo_needed=False,
        metrics_needed=False,
    )
    assert first["force_full_refresh"] is False

    _write(rubric, '{"v":2,"x":1}')
    second = refresh_decider.decide_refresh_actions(
        tmp_path,
        refresh_mode="auto",
        phase="baseline",
        hippo_needed=False,
        metrics_needed=False,
    )

    assert second["force_full_refresh"] is True
    assert "refresh-contract changed" in second["reasons"]


def test_decider_forces_full_refresh_on_large_structural_change(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARCH_FULL_REFRESH_INTERVAL", "99")
    monkeypatch.setattr(
        refresh_decider,
        "_collect_git_change_signals",
        lambda root: {
            "changed_total": 42,
            "structural_total": 12,
            "structural_ratio": 0.5,
            "trigger": True,
            "thresholds": {},
        },
    )

    out = refresh_decider.decide_refresh_actions(
        tmp_path,
        refresh_mode="auto",
        phase="baseline",
        hippo_needed=False,
        metrics_needed=False,
    )

    assert out["force_full_refresh"] is True
    assert out["hippo_refresh"] is True
    assert out["metrics_refresh"] is True
    assert "large structural change detected" in out["reasons"]
