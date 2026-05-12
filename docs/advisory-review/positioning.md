# 产品定位

`architec` 是建议型架构审查工具。

它回答的问题：

- 这份方案会触碰哪些架构边界？
- 这次代码改动引入或恶化了哪些结构风险？
- 当前项目长期健康状态如何变化？
- 针对一次审查结果，可以考虑哪些修复方向？

它不回答的问题：

- 这个功能应该怎么设计？
- 这次改动是否允许合入？
- 是否应该自动执行某个修复？
- 项目接下来应该优先做哪个重构？

## 输出语气

报告可以出现 `info`、`caution`、`high-concern` 这样的关注级别，但不能把它们解释为 `pass`、`fail` 或 `block`。

应使用：

- `info`
- `caution`
- `high-concern`
- `worth reviewing`
- `consider`
- `suggested adjustment`

应避免：

- `pass`
- `fail`
- `block`
- `violation`
- `must fix`
- `required before merge`

高风险项应表述为：

> high-concern: this change appears to expand a known hotspot and may increase maintenance risk.

而不是：

> failed: this change is blocked.

## 与其他工具的边界

`architec` 不替代 linter、type checker、test runner、coverage、CVE scanner 或 license scanner。

职责边界：

- linter 关注局部代码风格和简单错误。
- type checker 关注类型契约。
- test runner 和 coverage 关注行为验证。
- security / dependency 工具关注漏洞、许可和供应链。
- `architec` 关注项目级结构事实：组件边界、拓扑、历史漂移、方案一致性、AI 特有坏味和长期结构趋势。

`architec` 可以读取这些工具的报告作为补充证据，但不重建它们的能力。

## 范围

当前阶段聚焦 Python 项目。多语言扩展不在本阶段范围内，避免在核心审查信号尚未稳定前稀释产品能力。
