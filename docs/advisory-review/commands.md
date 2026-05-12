# 命令体系

公开入口收敛为四类：

```bash
archi plan-review <plan.md>
archi code-review --full .
archi code-review --diff .
archi code-review --since <ref> .
archi fix-advice --for <review.json>
archi status --trend
archi status --snapshot
```

命令职责：

- `plan-review`：审查方案 Markdown，输出方案风险和调整建议。细则见 [topics/plan-review.md](topics/plan-review.md)。
- `code-review`：审查代码，全量或增量输出结构健康、漂移信号和证据。细则见 [topics/code-review.md](topics/code-review.md)。
- `fix-advice`：基于一次审查结果输出可考虑的修复方向。细则见 [topics/fix-advice.md](topics/fix-advice.md)。
- `status`：展示长期状态、趋势和快照。细则见 [topics/status.md](topics/status.md)。

## 模式矩阵

| 命令 | 模式 | 是否互斥 | 读写行为 | 说明 |
| --- | --- | --- | --- | --- |
| `plan-review <plan.md>` | 单方案审查 | 不适用 | 读方案，写报告 | 当前版本只支持单个 plan 文件，不支持目录级多方案协同审查。 |
| `code-review --full` | 全量审查 | 与 `--diff` / `--since` 互斥 | 读项目，写报告 | 面向当前快照，展示整体健康状态和当前薄弱点。 |
| `code-review --diff` | 当前 diff 审查 | 与 `--full` / `--since` 互斥 | 读工作树 diff，写报告 | 只分析本次改动引入或恶化的问题。 |
| `code-review --since <ref>` | 指定引用后的增量审查 | 与 `--full` / `--diff` 互斥 | 读指定范围，写报告 | 只分析指定范围内的结构变化。 |
| `fix-advice --for <review.json>` | 修复建议 | 不适用 | 读 review，写建议报告 | 不生成 patch，不执行修改。 |
| `status --trend` | 趋势视图 | 可与只读选项组合 | 读历史事件和快照 | 展示跨时间变化，不审查具体改动。 |
| `status --snapshot` | 记录快照 | 与纯只读语义区分 | 读当前状态，写快照 | 这是写操作，用于记录状态锚点。 |

`status --trend` / `status --snapshot` 是 advisory project status 模式。既有 `archi status --json` 和裸 `archi status` 仍保留为 auth/session 状态查询，兼容策略见 [decisions/011-status-command-coexistence.md](decisions/011-status-command-coexistence.md)。

## 规则与约束来源

`plan-review` 和 `code-review` 需要知道架构边界、稳定性约束和禁向依赖。来源分三层：

- 默认推断：从包结构、import 图、public facade、命名习惯和既有组件描述中推断。
- 项目声明：可选 `architec.rules.yaml`，用于声明分层、稳定性等级、禁向依赖、热点保护和不建议扩大的模块。
- 运行产物：复用 Hippo snapshot、component descriptors、topology、hotspot digest、cleanup inventory 和 review 历史事件。

声明规则优先于推断规则。没有声明规则时，`architec` 仍可基于默认推断给出建议，但报告应标明相关 concern 的 confidence 较低或来源为 inferred。

共享输出契约见 [topics/evidence-model.md](topics/evidence-model.md)。审查信号取舍见 [topics/ai-signals.md](topics/ai-signals.md) 和 [topics/external-signals.md](topics/external-signals.md)。

## 旧功能迁移

| 现有入口 | 新定位 | 说明 |
| --- | --- | --- |
| `archi .` | `archi code-review --full .` | 全量架构分析转为全量代码审查建议。 |
| `archi --diff .` | `archi code-review --diff .` | 增量分析转为增量代码审查建议。 |
| `archi --goal ...` | parser 已移除 | 不再做目标规划；迁移到 `archi plan-review <plan.md>`。 |
| `archi gate` | parser 已移除 | `architec` 不做门禁、不输出放行裁决；迁移到 advisory `archi code-review --diff .`。 |
| `archi baseline` | parser 已移除 | 快照迁移到 `archi status --snapshot`。 |
| `archi cleanup` | parser 已移除 | cleanup / archive 成为 `archi code-review --full .` 审查报告中的 signals 和 file-level concerns。 |
| `archi archive` | `code-review` signal | archive 成为审查报告中的一类信号。 |
| `archi autofix` | parser 已移除 | 迁移到 `archi fix-advice --for <review.json>`；只给修复建议，不自动落地。 |
| `archi autofix --apply` | parser 已移除 | 不再提供自动修改行为。 |

迁移原则：

- 不长期保留会造成产品语义混乱的别名。
- breaking release 需要给出清晰命令映射表。
- 内部实现可以复用旧模块，但公开文档只讲新模型。
- 旧命令已完成 warning、soft-cut、parser removal 三段迁移；细节见 [decisions/010-legacy-command-migration-sequence.md](decisions/010-legacy-command-migration-sequence.md) 和 [decisions/016-legacy-parser-removal.md](decisions/016-legacy-parser-removal.md)。
- legacy wrapper public API 已按 [014](decisions/014-cleanup-subpackage-api-retire.md) 和 [015](decisions/015-root-legacy-public-api-retire.md) 退役；legacy CLI parser stubs 也已移除。
