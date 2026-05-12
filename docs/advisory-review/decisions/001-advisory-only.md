# Advisory-only Positioning

Date: 2026-05-12

## Context

`architec` 曾被讨论为 gate 或 CI 阻断工具，但 vibe coding 场景下，误伤一次就容易导致工具被绕过。当前更需要的是长期在场的项目级结构视角。

## Decision

`architec` 只输出分析、观察和建议，不输出放行裁决，不提供 gate 公开入口。

## Consequences

- 报告中不出现 pass/fail/block/must-fix 语义。
- 用户或团队可以自行把输出接入 CI，但阻断策略不属于 `architec` 产品语义。
- 价值叙事从“替你决定”转为“让你看见”。
