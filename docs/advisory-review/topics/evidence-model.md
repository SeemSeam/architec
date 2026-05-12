# 证据模型与输出契约

本文件定义建议型审查输出的共享数据结构。所有结构都避免 `pass`、`fail`、`block`、`must fix` 等裁决语义。

## 证据原则

- concern 必须尽量下沉到 `file:line`、根因符号或 import 边。
- 每条 high-concern 必须包含 evidence 和 confidence。
- code-review concern 不包含结构化修复方案；结构化修复建议只由 `fix-advice` 输出。
- `next_steps_hint` 只能是轻量提示，不能替代 `fix-advice`。
- `concerns[].evidence` 是每条 concern 的详细事实来源。
- 顶层 `evidence[]` 是从已展示 concerns 派生的轻量索引，不是第二份完整证据库。

## ReviewConcern

```json
{
  "concern_id": "",
  "kind": "",
  "level": "info|caution|high-concern",
  "confidence": 0.0,
  "location": {
    "path": "",
    "line": 0,
    "symbol": "",
    "symbol_kind": "function|class|module|import"
  },
  "root_cause": "",
  "evidence": [],
  "blast_radius": [],
  "next_steps_hint": ""
}
```

字段说明：

- `kind`：关注点类型，例如 `boundary`、`duplication`、`hotspot`、`cleanup`、`stability`、`missing-context`。
- `level`：关注级别，不代表门禁裁决。
- `confidence`：0 到 1 的证据置信度。
- `location`：尽量定位到文件、行、符号或 import 边。
- `evidence`：支撑该 concern 的事实证据。
- `blast_radius`：可能受影响的文件、符号、组件或调用者。
- `next_steps_hint`：轻量提示，不是结构化修复计划。

最低验收：

- 热点、cleanup、topology、plan-review concern 都能指到具体文件。
- 复杂度和重复实现类 concern 能尽量指到函数或类。
- 边界类 concern 能指到 import 边或 public API。
- 每条 high-concern 都必须包含 evidence 和 confidence。

## PlanReviewResult

```json
{
  "mode": "plan_review",
  "understood_plan": {
    "intent": "",
    "changes": [],
    "dependencies": []
  },
  "concerns": [],
  "suggested_adjustments": [],
  "plan_fingerprint": "",
  "artifacts": {}
}
```

`suggested_adjustments` 表达方案落地前可考虑的范围、位置、复用、测试或依赖调整，不是完整替代方案。

## CodeReviewResult

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

增量审查只输出本次新增或恶化的 concern，不混入历史旧账。

`summary` 字段约定：

- `concern_total`：top-N 截断前生成的 concern 总数。
- `top_concern_total`：主输出 `concerns[]` 中展示的 concern 数量。
- `concern_limit`：当前 top-N 上限。
- `signal_kinds`：本次输出中出现的 signal kind 列表。

`signals[]` 统一结构：

```json
{
  "kind": "cleanup|hotspot|topology|...",
  "summary": "",
  "metrics": {}
}
```

`evidence[]` 统一结构：

```json
{
  "evidence_id": "",
  "concern_id": "",
  "kind": "",
  "location": {},
  "confidence": 0.0,
  "facts": []
}
```

`evidence[]` 的条目从当前 `concerns[]` 派生。完整事实仍以 `concerns[].evidence` 为准；`evidence[]` 只提供便于 agent 快速扫描和引用的索引视图。

## FixAdviceResult

```json
{
  "mode": "fix_advice",
  "source_review": "",
  "suggestions": [
    {
      "target": "",
      "concern": "",
      "options": [],
      "tradeoffs": [],
      "risks": []
    }
  ],
  "artifacts": {}
}
```

`fix-advice` 不输出 patch，不包含 `apply` 字段，不承诺执行顺序。

## StatusResult

```json
{
  "mode": "status",
  "scores": {},
  "snapshot": {},
  "trend": {},
  "weakening_components": [],
  "artifacts": {}
}
```

首次运行且没有快照时，输出当前状态和空趋势说明。

## ReviewEvent

```json
{
  "generated_at": "iso8601",
  "mode": "plan_review|code_review|fix_advice|status",
  "review_type": "",
  "scores": {},
  "concern_counts": {},
  "top_concerns": [],
  "artifacts": {}
}
```

事件流默认写入 `.architec/review-events.jsonl`。

## 输出体量

- JSON 主体不含 artifacts 的目标大小小于 20KB。
- 默认只保留 top concerns 的完整 evidence，建议 N 不超过 5。
- 超出体量时，详细 findings、完整 evidence 和大图数据写入 artifacts，主输出保留摘要和路径。
- Markdown/HTML 可以更完整，但也应默认突出 top concerns。

## 事件流生命周期

- `review-events.jsonl` 是本地观察数据，不是强制提交到版本库的项目事实。
- 默认写入 `.architec/`，依赖项目现有 `.gitignore` 规则保持本地化。
- 是否纳入版本控制由项目自行决定。
- 文件达到 10MB 后应分片，例如 `review-events-YYYYMM.jsonl`。
- status 读取最近窗口内的事件，长期归档只用于离线趋势。
