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

- 当前分数和维度分。
- 与最近快照的对比。
- 趋势变化。
- 最近显著变化的归因。
- 跨时间的薄弱模块变化。

## 边界

- `status` 只观察长期状态，不审查具体改动。
- `status` 不给修复建议。
- 基线或快照管理归入 `status`，不再保留独立 `baseline` 命令。
- `code-review --full` 展示当前快照的薄弱模块；`status` 展示薄弱模块如何随时间变化。

## 空/降级输出

- 首次运行且没有快照时，展示当前状态，并提示可用 `status --snapshot` 记录状态锚点。
- 没有历史事件时，`--trend` 输出空趋势和说明，不合成趋势。

## 事件流

每次 review 可追加摘要到 `.architec/review-events.jsonl`。事件流用于趋势视图和增量审查的连续性提示。

事件流生命周期见 [evidence-model.md](evidence-model.md)。
默认策略见 [decisions/009-review-event-lifecycle.md](../decisions/009-review-event-lifecycle.md)：事件本地保存，依赖 `.architec/` 忽略规则，达到 10MB 后按月份分片。
