# Single Plan File Review

Date: 2026-05-12

## Context

方案审查的关键输入是用户已有方案。若一开始支持目录级、多方案协同审查，会显著增加解析和一致性判断复杂度。

## Decision

`plan-review` 当前只支持单个方案 Markdown 文件作为审查输入。

## Consequences

- 多 plan 协同审查不进入 4-6 周范围。
- 推荐模板需要让单个 Markdown 足以表达 intent、changes、dependencies 和 notes。
- 方案目录管理由 `plan-tree` skill 承担，不属于 `architec plan-review` 的职责。
