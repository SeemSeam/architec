# 未决项

这些问题还没有形成稳定决策。它们不是 todo，而是后续讨论需要收敛的点。

- 无发现场景的输出文案是否需要进一步标准化到每个命令的 schema 示例中。
- JSON 主体 20KB 目标是否适合中大型仓库，是否需要按命令设置不同体量目标。
- `shadow_implementation` 的相似度阈值应如何在低误报和高召回之间取平衡。
- `concern_id` 应作为跨运行稳定标识，还是作为排序后位置编号；这会影响后续 `fix-advice` 引用方式。
- `code-review --diff` 的 LLM preflight 集合是否应按 advisory 场景精简，避免未来作为轻量反馈工具时延迟过高。
- `code-review --since` 的底层 git diff helper 在引用解析失败时是否应返回结构化错误，而不是静默回退为空 diff。
- 顶层 human summary 在 CodeReviewResult 下是否需要重写，以恢复 cleanup/archive/signals/top-concerns 等 advisory-only 摘要信息。
- `fix-advice --for <review.json>` 是否长期保留 `--for`，还是改为更直白但稍长的 `--review <review.json>`。
- `fix-advice` 读取 review JSON 失败时是否应返回 CLI 错误，而不是静默降级为空 suggestions。
- `fix-advice` 是否应写入 review event，还是保持为纯消费型命令。
- `near_duplicate` 落地后是否需要同步补 `fix-advice` 的 `duplication` 专用建议分支。
- 第一阶段结束后是否启动 TypeScript/Go 多语言调研。
