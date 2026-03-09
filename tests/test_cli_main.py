from __future__ import annotations

import sys

import architec.cli as cli


def test_build_parser_accepts_trailing_path():
    parser = cli.build_parser()
    args = parser.parse_args(["--goal", "review", "--diff", "--base", "main", "--head", "HEAD", "."])
    assert args.goal == "review"
    assert args.diff is True
    assert args.base == "main"
    assert args.head == "HEAD"
    assert args.path == "."


def test_main_rejects_base_without_diff(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["architec", "--base", "main"])
    assert cli.main() == 2
    assert "--base/--head require --diff" in capsys.readouterr().err
