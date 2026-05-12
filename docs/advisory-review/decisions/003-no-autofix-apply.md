# No Automatic Apply

Date: 2026-05-12

## Context

自动修改会让 `architec` 从建议工具变成执行工具，增加误解和责任边界问题。当前产品定位要求工具只提供可采纳的建议。

## Decision

移除 `autofix --apply` 公开语义。`fix-advice` 只输出文字化、结构化的修复建议，不生成 patch，不执行修改。

## Consequences

- 修复是否执行由人或 coding agent 决定。
- 每条建议可以独立采纳。
- `fix-advice` 不承诺执行顺序，也不输出可直接 apply 的补丁。
