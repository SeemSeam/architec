from __future__ import annotations

import locale

from architec import i18n


def _clear_language_env(monkeypatch) -> None:
    for name in ("ARCHITEC_LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        monkeypatch.delenv(name, raising=False)


def test_detects_chinese_from_locale_env(monkeypatch) -> None:
    _clear_language_env(monkeypatch)
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")

    assert i18n.current_language() == "zh"
    assert i18n.tr("self_manage.update_available_yes", "Update available: yes") == "有可用更新：是"


def test_detects_chinese_from_lc_messages(monkeypatch) -> None:
    _clear_language_env(monkeypatch)
    monkeypatch.setenv("LC_MESSAGES", "zh_TW.UTF-8")
    monkeypatch.setenv("LANG", "en_US.UTF-8")

    assert i18n.current_language() == "zh"


def test_architec_lang_can_force_english_over_chinese_locale(monkeypatch) -> None:
    _clear_language_env(monkeypatch)
    monkeypatch.setenv("LC_ALL", "zh_CN.UTF-8")
    monkeypatch.setenv("ARCHITEC_LANG", "en")

    assert i18n.current_language() == "en"
    assert i18n.tr("self_manage.update_available_yes", "Update available: yes") == "Update available: yes"


def test_architec_lang_can_force_chinese_over_english_locale(monkeypatch) -> None:
    _clear_language_env(monkeypatch)
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("ARCHITEC_LANG", "zh")

    assert i18n.current_language() == "zh"


def test_unknown_locale_falls_back_to_english(monkeypatch) -> None:
    _clear_language_env(monkeypatch)
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    monkeypatch.setattr(locale, "getlocale", lambda _category=None: (None, None))

    assert i18n.current_language() == "en"


def test_argparse_error_message_localizes_common_patterns(monkeypatch) -> None:
    monkeypatch.setenv("ARCHITEC_LANG", "zh")

    assert i18n.localize_argparse_error("unrecognized arguments: --goal") == "无法识别的参数：--goal"
