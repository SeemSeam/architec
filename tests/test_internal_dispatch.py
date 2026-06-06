from __future__ import annotations

from architec.integration import internal_dispatch


def test_dispatch_internal_hippos_command(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args):
        calls.append(list(args))
        return 7

    monkeypatch.setattr(internal_dispatch, "run_bundled_hippos", fake_run)

    assert internal_dispatch.dispatch_internal_command(
        [internal_dispatch.INTERNAL_HIPPOS_COMMAND, "init", "."]
    ) == 7
    assert calls == [["init", "."]]


def test_dispatch_internal_collect_metrics_command(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args):
        calls.append(list(args))
        return 0

    monkeypatch.setattr(internal_dispatch, "run_bundled_collect_metrics", fake_run)

    assert internal_dispatch.dispatch_internal_command(
        [internal_dispatch.INTERNAL_COLLECT_METRICS_COMMAND, "--root", "."]
    ) == 0
    assert calls == [["--root", "."]]


def test_dispatch_internal_command_ignores_normal_argv():
    assert internal_dispatch.dispatch_internal_command(["--version"]) is None
