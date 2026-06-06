from __future__ import annotations

import locale
import os
from typing import Any


SUPPORTED_LANGUAGES = {"en", "zh"}
DEFAULT_LANGUAGE = "en"
LANGUAGE_OVERRIDE_ENV = "ARCHITEC_LANG"


_ZH_TRANSLATIONS = {
    "argparse.error": "错误",
    "argparse.help": "显示此帮助信息并退出",
    "argparse.options": "选项",
    "argparse.positional_arguments": "位置参数",
    "argparse.unrecognized_arguments": "无法识别的参数：{args}",
    "argparse.not_allowed_with_argument": "{argument} 不能与 {conflict} 同时使用",
    "archive.label": "归档",
    "artifacts.archive_candidates": "归档候选",
    "artifacts.archive_summary": "归档摘要",
    "artifacts.cleanup_inventory": "清理清单",
    "artifacts.cleanup_ledger": "清理台账",
    "artifacts.cleanup_summary": "清理摘要",
    "artifacts.header": "产物：",
    "artifacts.json": "JSON",
    "artifacts.semantic_judge": "语义判断",
    "artifacts.semantic_judge_summary": "语义判断摘要",
    "artifacts.summary": "摘要",
    "artifacts.viz": "可视化",
    "cli.advice_feedback_requires_full": "--advice-feedback 当前需要与 --full 一起使用",
    "cli.advice_feedback_with_check": "--advice-feedback 不能与 --check 一起使用",
    "cli.analysis_complete": "Archi 分析完成",
    "cli.base_head_require_diff": "--base/--head 需要与 --diff 一起使用",
    "cli.checks": "LLM 检查",
    "cli.cleanup": "清理",
    "cli.cleanup.categories": "清理类别",
    "cli.cleanup.metadata": "清理元数据",
    "cli.concerns": "关注点",
    "cli.description": "Archi 架构分析 CLI",
    "cli.epilog": "维护命令：`archi update` 和 `archi uninstall`。",
    "cli.full_and_diff": "--full 和 --diff 不能同时使用",
    "cli.help.check": "验证后端 LLM 配置并退出",
    "cli.help.full": "运行全项目 LLM 架构审查",
    "cli.help.out": "可选的输出 JSON 路径覆盖",
    "cli.help.path": "项目根目录",
    "cli.help.refresh": "分析前强制刷新 Hippos bundle",
    "cli.help.version": "显示当前 CLI 版本和最新发布状态",
    "cli.hippos.bundle": "Hippos bundle",
    "cli.hippos_bundle_unavailable": "Hippos bundle 不可用",
    "cli.hippos_refreshed": "已刷新",
    "cli.llm_unavailable": "后端 LLM 不可用",
    "cli.path": "路径",
    "cli.plan_review_requires_incremental": "--plan-review 需要增量审查",
    "cli.plan_review_with_check": "--plan-review 不能与 --check 一起使用",
    "cli.plan_review_with_full": "--plan-review 需要 --diff 或 --since",
    "cli.preflight_ok": "Archi 预检通过",
    "cli.progress.check_llm": "archi [2/3] 检查后端 LLM 配置",
    "cli.progress.code_review_diff": "archi code-review [3/3] 运行 diff 代码审查",
    "cli.progress.code_review_full": "archi code-review [3/3] 运行全量代码审查",
    "cli.progress.code_review_since": "archi code-review [3/3] 运行 since 代码审查",
    "cli.progress.fix_advice": "archi fix-advice [1/1] 读取审查结果",
    "cli.progress.incremental_llm": "archi [3/3] 运行增量 LLM 代码审查",
    "cli.progress.plan_review": "archi plan-review [1/1] 读取计划",
    "cli.progress.preflight_complete": "archi [3/3] 预检完成",
    "cli.progress.refresh_bundle": "archi [1/3] 刷新 Hippos bundle",
    "cli.progress.status_snapshot": "archi status [1/1] 写入建议型项目状态快照",
    "cli.progress.status_trend": "archi status [1/1] 读取建议型项目状态趋势",
    "cli.progress.static_diff_review": "archi code-review [3/3] 运行静态 diff 代码审查",
    "cli.progress.static_full_review": "archi code-review [3/3] 运行静态全量代码审查",
    "cli.progress.static_since_review": "archi code-review [3/3] 运行静态 since 代码审查",
    "cli.progress.validate_bundle": "archi [1/3] 验证现有 Hippos bundle",
    "cli.progress.bundle_missing_refresh": "archi [1/3] Hippos bundle 缺失，正在通过 hippos 刷新",
    "cli.progress.bundle_stale_refresh": "archi [1/3] Hippos bundle 过期，正在通过 hippos 刷新",
    "cli.removed_command": "archi {command} 命令解析器已移除；请使用 `{replacement}`。",
    "cli.risk_context_with_check": "--risk-context 不能与 --check 一起使用",
    "cli.scores": "评分",
    "cli.semantic_judge": "语义判断",
    "cli.signals": "信号：",
    "cli.summary": "摘要",
    "cli.top_concerns": "主要关注点：",
    "cli.top_improvements": "主要改进：",
    "cli.unknown_path": "未知路径",
    "count.limit": "上限",
    "count.shown": "显示",
    "count.total": "总数",
    "label.candidates": "候选",
    "label.expires_at": "expires_at",
    "label.expired": "已过期",
    "label.governance": "治理",
    "label.incremental": "增量",
    "label.overall": "总体",
    "label.owner": "owner",
    "label.ready": "就绪",
    "label.review": "需复核",
    "label.review_required": "需复核",
    "label.reviewed": "已审查",
    "label.status": "状态",
    "label.structure": "结构",
    "label.ttl": "ttl",
    "label.full": "全量",
    "llm_preflight.failed": "Architec LLM 预检失败：",
    "llm_preflight.hint": (
        "提示：请在 ~/.llmgateway/config.yaml 中配置 provider 凭据、strong_model 和 weak_model。"
        "可选的 Architec 任务覆盖可以放在 ~/.architec/config.yaml 或项目 .architec/config.yaml。"
    ),
    "llm_preflight.missing_api_key": "缺少 api_key",
    "llm_preflight.missing_base_url": "api_style={api_style} 需要 base_url",
    "llm_preflight.no_candidate": "未配置后端 LLM 候选",
    "self_manage.already_latest_reinstalling": "当前版本已是最新发布；正在重新安装 {version}。",
    "self_manage.cli_version": "Architec CLI 版本：{version}",
    "self_manage.config_purge": "配置清理：已启用",
    "self_manage.config_purge_disabled": "配置清理：未启用；已保留 ~/.architec、~/.hippos、~/.hippocampus 和 ~/.llmgateway。",
    "self_manage.current_version": "当前版本：{version}",
    "self_manage.description": "Architec 维护命令",
    "self_manage.help.purge_config": "同时删除 Architec/Hippos/llmgateway 配置目录",
    "self_manage.help.uninstall": "移除已安装的 Architec launcher 和托管资产",
    "self_manage.help.update": "重新安装最新公开 Architec 构建",
    "self_manage.help.yes": "跳过交互确认提示",
    "self_manage.installer_refresh_unverified": "由于无法验证最新元数据，将继续刷新安装器。",
    "self_manage.latest_check_failed": "最新版本检查失败：{error}",
    "self_manage.latest_release": "最新发布：{version}",
    "self_manage.latest_release_unknown": "最新发布：未知",
    "self_manage.latest_version": "最新版本：{version}",
    "self_manage.latest_version_unknown": "最新版本：未知",
    "self_manage.no_artifacts": "未找到 Architec 安装产物。",
    "self_manage.non_interactive_yes": "非交互卸载需要 --yes。",
    "self_manage.python_deps_purge": "托管 Python 依赖环境清理：已启用",
    "self_manage.removed": "已移除：",
    "self_manage.remove_prompt": "从 {path} 移除 Architec？[y/N]: ",
    "self_manage.run": "运行：{command}",
    "self_manage.running_installer": "正在运行安装器：{url}",
    "self_manage.uninstall_complete": "Architec 卸载完成。",
    "self_manage.update_available_no": "有可用更新：否",
    "self_manage.update_available_yes": "有可用更新：是",
    "self_manage.update_completed": "Architec 更新完成。",
    "self_manage.warning_latest": "警告：无法解析最新发布版本：{error}",
}


TRANSLATIONS = {
    "zh": _ZH_TRANSLATIONS,
}


def _normalize_language(value: str) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    first = raw.split(":", 1)[0].split(".", 1)[0].replace("-", "_")
    if first.startswith("zh"):
        return "zh"
    if first.startswith("en") or first in {"c", "posix"}:
        return "en"
    return ""


def current_language() -> str:
    override = _normalize_language(os.environ.get(LANGUAGE_OVERRIDE_ENV, ""))
    if override in SUPPORTED_LANGUAGES:
        return override

    for env_name in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        lang = _normalize_language(os.environ.get(env_name, ""))
        if lang in SUPPORTED_LANGUAGES:
            return lang

    for category in (getattr(locale, "LC_MESSAGES", None), locale.LC_CTYPE):
        if category is None:
            continue
        try:
            lang = _normalize_language(locale.getlocale(category)[0] or "")
        except Exception:
            continue
        if lang in SUPPORTED_LANGUAGES:
            return lang

    return DEFAULT_LANGUAGE


def tr(key: str, default: str, **values: Any) -> str:
    text = TRANSLATIONS.get(current_language(), {}).get(key, default)
    if values:
        return text.format(**values)
    return text


def localize_argparse_error(message: str) -> str:
    if current_language() != "zh":
        return message
    raw = str(message or "")
    if raw.startswith("unrecognized arguments: "):
        return tr(
            "argparse.unrecognized_arguments",
            raw,
            args=raw.removeprefix("unrecognized arguments: "),
        )
    marker = ": not allowed with argument "
    if raw.startswith("argument ") and marker in raw:
        argument, conflict = raw.removeprefix("argument ").split(marker, 1)
        return tr(
            "argparse.not_allowed_with_argument",
            raw,
            argument=argument,
            conflict=conflict,
        )
    return raw


def localize_argparse_parser(parser: Any) -> Any:
    if current_language() != "zh":
        return parser
    positionals = getattr(parser, "_positionals", None)
    if positionals is not None:
        positionals.title = tr("argparse.positional_arguments", "positional arguments")
    optionals = getattr(parser, "_optionals", None)
    if optionals is not None:
        optionals.title = tr("argparse.options", "options")
    for action in getattr(parser, "_actions", []):
        if getattr(action, "dest", "") == "help":
            action.help = tr("argparse.help", "show this help message and exit")
    return parser
