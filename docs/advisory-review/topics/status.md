# status 状态与趋势

`status` 展示长期状态、趋势和快照。它不审查具体改动，不给修复建议。

## 输入

```bash
archi status --trend
archi status --snapshot
```

模式：

- `--trend`：读取历史事件和快照，展示趋势。
- `--snapshot`：读取当前状态并写入快照。这是写操作。

## 输出

- 当前分数和维度分，来源是最近一次 `review_type == "full"` 的 code-review event。
- 与最近快照的对比。
- 趋势变化。
- 最近显著变化的归因。
- 跨时间的薄弱模块变化。

## 边界

- `status` 只观察长期状态，不审查具体改动。
- `status` 不给修复建议。
- 基线或快照管理归入 `status`，不再保留独立 `baseline` 命令。
- `code-review --full` 展示当前快照的薄弱模块；`status` 展示薄弱模块如何随时间变化。
- `code-review --diff` 和 `code-review --since` 参与趋势计数和薄弱模块观察，但不作为 status scores 来源。
- `fix-advice` 是 review JSON 的消费型命令，不写 review event。

## 空/降级输出

- 首次运行且没有快照时，展示当前状态，并提示可用 `status --snapshot` 记录状态锚点。
- 没有历史事件时，`--trend` 输出空趋势和中性说明：`No review events were recorded.`，不合成趋势。
- 没有 full code-review event 时，`scores` 为空，并在 `trend.score_source` 中标记为 `none`；summary 使用 `No full code-review events were recorded for status scores.`
- 这些 empty states 不是项目健康 verdict，只说明当前事件输入不足或未记录。

## 事件流

每次 review 可追加摘要到 `.architec/review-events.jsonl`。事件流用于趋势视图和增量审查的连续性提示。

事件流生命周期见 [evidence-model.md](evidence-model.md)。
默认策略见 [decisions/009-review-event-lifecycle.md](../decisions/009-review-event-lifecycle.md)：事件本地保存，依赖 `.architec/` 忽略规则，达到 10MB 后按月份分片。

当前 status trend 默认读取最近 100 条 event，不做时间窗口过滤。`weakening_components` 按 mention count 降序、path 升序稳定排序。详细语义见 [decisions/019-status-event-semantics.md](../decisions/019-status-event-semantics.md)。
