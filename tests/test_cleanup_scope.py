from __future__ import annotations

from architec.cleanup.scope import classify_cleanup_path, iter_cleanup_scope


def test_classify_cleanup_path_distinguishes_prompt_config_script_doc_and_source() -> None:
    assert classify_cleanup_path("src/app.py") == "source"
    assert classify_cleanup_path("tools/migrate.sh") == "script"
    assert classify_cleanup_path("docs/cleanup-plan.md") == "doc"
    assert classify_cleanup_path("config/service.toml") == "config"
    assert classify_cleanup_path("prompts/system.md") == "prompt"
    assert classify_cleanup_path("tests/test_app.py") is None
    assert classify_cleanup_path("assets/logo.png") is None


def test_iter_cleanup_scope_scans_default_kinds_and_applies_archi_rules(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tools").mkdir()
    (tmp_path / "docs" / "legacy").mkdir(parents=True)
    (tmp_path / "config").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "tools" / "migrate.py").write_text("print('tool')\n", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text("# guide\n", encoding="utf-8")
    (tmp_path / "docs" / "legacy" / "old.md").write_text("# old\n", encoding="utf-8")
    (tmp_path / "config" / "service.toml").write_text("name = 'svc'\n", encoding="utf-8")
    (tmp_path / "prompts" / "review.md").write_text("# prompt\n", encoding="utf-8")
    (tmp_path / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / ".architecture-rules.toml").write_text(
        "\n".join(
            [
                "[archi]",
                'ignore_paths = ["docs/legacy"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    entries = iter_cleanup_scope(tmp_path)
    pairs = {(item.path, item.kind) for item in entries}

    assert ("src/app.py", "source") in pairs
    assert ("tools/migrate.py", "script") in pairs
    assert ("docs/guide.md", "doc") in pairs
    assert ("config/service.toml", "config") in pairs
    assert ("prompts/review.md", "prompt") in pairs
    assert ("docs/legacy/old.md", "doc") not in pairs
    assert all(path != "assets/logo.png" for path, _kind in pairs)
