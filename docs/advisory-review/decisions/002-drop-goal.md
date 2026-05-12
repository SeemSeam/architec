# Drop Public Goal Planning

Date: 2026-05-12

## Context

原 `goal` 能力容易被理解为“根据一句目标生成规划”。这与新的建议型审查定位冲突，也和 coding agent 的规划能力重叠。

## Decision

移除 `goal` 公开入口。相关的目标相关性分析能力可以作为 `plan-review` 的内部实现复用，但不再作为规划命令暴露。

## Consequences

- `architec` 不负责提出方案。
- 用户提供方案 Markdown，`architec` 只审查方案会撞上的项目事实和结构风险。
- 文档和帮助信息不再使用 `goal` 作为主入口。
