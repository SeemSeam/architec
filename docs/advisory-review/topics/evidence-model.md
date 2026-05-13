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
  "references": [],
  "blast_radius": [],
  "next_steps_hint": ""
}
```

字段说明：

- `concern_id`：concern 的引用标识，不表达排序位置。当前 code-review 生成的 id 使用 `code-review:<kind>:<hash>`，hash 来自 kind、source mapper、primary location、facts 和可用 reference/fingerprint 等事实。旧 review 中没有稳定 hash 格式的 id 仍合法。
- `kind`：关注点类型，例如 `boundary`、`duplication`、`shadow-implementation`、`hotspot`、`cleanup`、`stability`、`missing-context`。
- `level`：关注级别，不代表门禁裁决。
- `confidence`：0 到 1 的证据置信度。
- `location`：尽量定位到文件、行、符号或 import 边。
- `evidence`：支撑该 concern 的事实证据。
- `references`：可选结构化相关位置列表，用于表达 reference implementation、caller、callee 等关系。旧 concern 没有该字段仍合法。
- `blast_radius`：可能受影响的文件、符号、组件或调用者。
- `next_steps_hint`：轻量提示，不是结构化修复计划。

`references[]` 统一使用 location-like 对象，并可带 `role`：

```json
{
  "role": "reference|existing_implementation",
  "path": "",
  "line": 0,
  "symbol": "",
  "symbol_kind": "function|class|module|import"
}
```

例如 `near_duplicate` duplication concern 的 `location` 指向 duplicate implementation，`references[]` 使用 `role: "reference"` 指向 reference implementation。`shadow-implementation` concern 的 `location` 指向疑似 shadow implementation，`references[]` 使用 `role: "existing_implementation"` 指向可对照的已有实现；函数级 concern 使用 `location.symbol_kind: "function"`，类级 concern 使用 `location.symbol_kind: "class"`。`fix-advice` 按 role 区分 duplication reference 和 shadow existing implementation，不把两者混用。`concerns[].evidence` 中保留字符串事实以兼容旧消费者，但新消费者应优先读取结构化 `references[]`。

在 diff/since scoped review 中，`shadow-implementation` 和 `near_duplicate` 的 `location.path` 必须位于 changed files；`references[]` 可以指向未变更文件。对应 signal metrics 使用 `scoped_to_changed_files`、`changed_file_total` 和 `candidate_total_before_scope` 标识它不是全仓总量。`near_duplicate` 的 scope 条件只看 primary `location.path`，不因为 reference path changed 而报告历史旧账。

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

`review_type == "since"` 且引用或 range 不可解析时，仍返回 CodeReviewResult 骨架：`concerns` 和 `findings` 为空，`summary.headline` 说明无法分析该 since range，`summary.reason` 记录输入范围不可解析。

`summary` 字段约定：

- `concern_total`：top-N 截断前生成的 concern 总数。
- `top_concern_total`：主输出 `concerns[]` 中展示的 concern 数量。
- `concern_limit`：当前 top-N 上限。
- `signal_kinds`：本次输出中出现的 signal kind 列表。
- `payload_bytes`：不含 `artifacts` 的主 JSON compact encoding 估算字节数，用于观察输出体量。

`concerns[]` 是默认展示 portfolio，不是完整 concern truth。排序先保留 severity level 优先级，再在同一 level 内尽量展示不同 kind；需要完整集合的消费者应结合 artifacts 或扩展输出，而不是只读取 top-N。

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

为控制主 JSON 体量，展示层会限制每条 concern 的 `evidence`、`references` 和 `blast_radius` 条数，并限制过长的一层 signal metric map。发生截断时，`artifacts.payload_truncation` 记录原始条数和保留条数。该截断不改变 `concern_id`，也不改变 `summary.concern_total`。

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

如果输入的 review JSON 不存在、不是合法 JSON，或顶层不是 object，CLI 应返回错误并保持 stdout 为空。合法 review 但没有 concerns 时，输出空 `suggestions` 是正常结果。

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

没有 review events 时，输出空趋势说明。

`scores` 来自最近一条 full code-review event。没有 full event 时，`scores` 为空，并通过 `trend.score_source: "none"` 说明来源缺失。`trend.event_limit` 记录当前默认读取窗口，现阶段为最近 100 条 events。

## ReviewEvent

```json
{
  "generated_at": "iso8601",
  "mode": "code_review",
  "review_type": "",
  "scores": {},
  "concern_counts": {},
  "top_concerns": [],
  "artifacts": {}
}
```

事件流默认写入 `.architec/review-events.jsonl`。

当前事件生产者是 `code-review`。`fix-advice` 读取 review JSON 后输出建议，但不写 review event，因为它不代表项目结构状态变化。其他命令如果要写 event，需要单独决策。

## 输出体量

- JSON 主体不含 artifacts 的目标大小小于 20KB；这是 advisory target，不是 hard gate。
- 默认只保留 top concerns 的完整 evidence，建议 N 不超过 5。
- 超出体量时，详细 findings、完整 evidence 和大图数据写入 artifacts，主输出保留摘要和路径。
- Markdown/HTML 可以更完整，但也应默认突出 top concerns。

## 事件流生命周期

- `review-events.jsonl` 是本地观察数据，不是强制提交到版本库的项目事实。
- 默认写入 `.architec/`，依赖项目现有 `.gitignore` 规则保持本地化。
- 是否纳入版本控制由项目自行决定。
- 文件达到 10MB 后应分片，例如 `review-events-YYYYMM.jsonl`。
- status 读取最近 100 条事件，长期归档只用于离线趋势。
- code-review event 写入对 `OSError` fail-open：主 review result 正常返回，并在 artifacts 中记录 `review_event_error`。
