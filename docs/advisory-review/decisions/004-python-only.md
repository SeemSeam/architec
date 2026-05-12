# Python-only First Stage

Date: 2026-05-12

## Context

多语言支持会放大分析、证据模型和信号实现的复杂度。在 Python 场景下把建议质量做稳，比过早扩语言更重要。

## Decision

当前阶段聚焦 Python 项目。TypeScript、Go 等多语言扩展不进入 4-6 周范围。

## Consequences

- 规则、信号、证据模型优先服务 Python 包结构、import 图和符号分析。
- 文档需要明确多语言不在本阶段范围。
- 等核心审查能力稳定后再评估多语言。
