# code-review 代码审查

`code-review` 审查代码结构风险。它不输出 pass/fail，不做门禁，不自动调用修复建议。

## 输入

```bash
archi code-review --full .
archi code-review --diff .
archi code-review --since <ref> .
```

模式关系：

- `--full`、`--diff`、`--since` 互斥。
- `--full` 面向当前项目快照。
- `--diff` 面向当前工作树改动。
- `--since <ref>` 面向指定引用后的变更范围。

## 输出

```json
{
  "mode": "code_review",
  "review_type": "full|diff|since",
  "scores": {},
  "summary": {},
  "findings": [],
  "signals": [],
  "evidence": [],
  "concerns": [],
  "artifacts": {}
}
```

## 全量审查

全量审查语境：

- 对项目做一次体检。
- 发版前了解整体健康状态。
- 接手陌生项目时快速建立结构认知。

输出重点：

- 当前总分和维度分。
- 按组件或包聚合的健康状态。
- 当前快照里的薄弱模块列表。
- 主要结构热点。
- cleanup、archive、重复实现、shadow implementation、边界漂移等信号。

全量审查可以给出结构叙事：

- 组件之间的相对健康度排名。
- 最薄弱模块在项目里的相对位置。
- 2-3 条值得关注的结构叙事。
- top concerns，完整清单放 artifacts。

全量审查中的 AI/vibe coding 信号当前包括：

- `near_duplicate`：规范化 AST 指纹重复，输出 `duplication` concern，并通过 `references[]` 标出 reference implementation。
- `shadow_implementation`：函数级和类级跨文件相似实现，输出 `shadow-implementation` concern，并通过 `references[]` 标出 `existing_implementation`。

`near_duplicate` 和 `shadow_implementation` 在增量模式中只报告 `location.path` 位于 changed files 的 concern，`references[]` 可以指向未变更的 existing/reference implementation。`near_duplicate` 不因为 reference path changed 而报告历史旧账。

## 增量审查

增量审查语境：

- coding agent 写完后自检。
- PR 或变更集的信息性反馈。
- 方案落地后的偏离观察。

输出重点：

- 本次改动引入或恶化的问题。
- 各维度 delta。
- 归因到文件或符号的 evidence。
- 新增信号，而不是历史已有信号。
- 若有关联方案指纹，输出方案一致性观察。

增量模式必须严格控制范围，只谈本次变化。历史债务应放在全量审查或 `status` 中呈现。

## 空/降级输出

- 如果增量审查没有发现新增或恶化的问题，输出空 `findings` 和明确摘要：`No new architecture concerns were identified in this diff.`
- 如果 `--since <ref>` 的引用或 range 不可解析，输出结构化 CodeReviewResult 降级对象，不回退到全量审查或无关工作树 diff。
- 如果关联方案指纹不可读取，只跳过方案一致性观察，保留普通 code-review 输出。

## LLM Preflight

advisory code-review 的 full、diff、since 模式使用同一组基础 LLM preflight checks。diff/since 不额外要求 `architect_component_scoring` preflight，以保持增量反馈轻量；底层分析仍可在运行时复用 component scoring 能力。

## 排序和边界

concern 排序由影响面、置信度和趋势共同决定。可修复性属于 `fix-advice` 范畴，不作为 `code-review` 排序因子。

`code-review --full` 展示当前快照的薄弱模块；`status` 展示薄弱模块如何随时间变化。

## 输出计数

`concerns[]` 默认只展示 top concerns。`summary.concern_total` 记录截断前总数，`summary.top_concern_total` 记录本次展示数量，`summary.concern_limit` 记录 top-N 上限。

`signals[]` 只用 `kind`、`summary`、`metrics` 三个通用字段；信号专属数据放进 `metrics`，避免每类 signal 发明不同顶层字段。

`concern_id` 是基于事实生成的引用标识，不代表展示顺序。当前生成格式为 `code-review:<kind>:<hash>`；hash 输入来自 mapper source、primary location、evidence，以及 duplication reference/fingerprint 等事实。
