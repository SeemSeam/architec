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
- `kind`：关注点类型，例如 `boundary`、`architecture-contract`、`plan-diff-consistency`、`duplication`、`shadow-implementation`、`hotspot`、`cleanup`、`stability`、`missing-context`。
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

例如 `near_duplicate` duplication concern 的 `location` 指向 duplicate implementation，`references[]` 使用 `role: "reference"` 指向 reference implementation。`shadow-implementation` concern 的 `location` 指向疑似 shadow implementation，`references[]` 使用 `role: "existing_implementation"` 指向可对照的已有实现；函数级 concern 使用 `location.symbol_kind: "function"`，类级 concern 使用 `location.symbol_kind: "class"`。file/module-level shadow implementation 目前只做 internal dry-run metrics，不进入 ReviewConcern，也不新增 `symbol_kind: "module"` 的 shadow concern。`fix-advice` 按 role 区分 duplication reference 和 shadow existing implementation，不把两者混用。`concerns[].evidence` 中保留字符串事实以兼容旧消费者，但新消费者应优先读取结构化 `references[]`。

`near_duplicate` 不为委托目标不同的 thin wrapper/facade boilerplate 输出 concern。该过滤发生在 concern 构建之前，因此不会改变已输出 concern 的 schema、`concern_id` 格式或 `references[].role` 语义。

`shadow_implementation` 不为清晰的 renderer versus assembler/support/budget/context split-role pairs 输出 concern。该 role taxonomy filtering 发生在 concern 构建之前；已输出的 `shadow-implementation` concern 仍使用同一 schema、`references[].role: "existing_implementation"`、函数/类 `location.symbol_kind` 和事实型 `concern_id`。parser-helper pairs 和 same-role candidates 仍可报告；file/module-level shadow public signal 仍 deferred。

在 diff/since scoped review 中，`shadow-implementation` 和 `near_duplicate` 的 `location.path` 必须位于 changed files；`references[]` 可以指向未变更文件。对应 signal metrics 使用 `scoped_to_changed_files`、`changed_file_total` 和 `candidate_total_before_scope` 标识它不是全仓总量。`near_duplicate` 的 scope 条件只看 primary `location.path`，不因为 reference path changed 而报告历史旧账。

`architecture-contract` concern 的 `location` 指向 changed file 中的 import 行，`evidence` 至少包含 `architecture_contract.rule_id`、`architecture_contract.source_glob`、`architecture_contract.import` 和 `architecture_contract.restricted_import`。规则的 `note` 属于 human guidance，进入 `next_steps_hint` 而不是 evidence。没有 `.architecture-rules.toml` contract config 时，code-review 不输出 contract signal 或 concern。

`fix-advice` 会为 `architecture-contract` concern 消费这些 factual evidence，并把 `next_steps_hint` 作为可选 review context。它不把 rule note 当作 evidence，也不判断 contract 或 changed import 哪一方正确。

`plan-diff-consistency` concern 的 `location` 指向计划外 changed file、计划中未触达的路径，或缺失计划 import expectation 的相关 changed file/source scope。`evidence` 至少包含 `plan_diff_consistency.observation` 和对应的 changed/planned path 或 `planned_import` facts。它只表达 saved plan-review JSON 与 selected diff 的不一致，不表达 correctness 或 merge readiness。

`risk_context` facts 是外部报告提供的 companion evidence。它们可以附加到既有 concern 的 `evidence[]`，例如 `risk_context.coverage=0.42`、`risk_context.churn=13`、`risk_context.related_test_total=0`、`risk_context.complexity=18`、`risk_context.public_api=true` 或 `risk_context.recurrence=3`。这些 facts 不参与 `concern_id` 生成，不改变 concern ranking，也不表示行为正确性。Risk context 不创建新 concern；未匹配到既有 concern 的外部文件事实只进入 input counts。

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

For `review_type: "diff"` and `review_type: "since"`, the displayed
`concerns[]` portfolio should be selected-scope first. A selected-scope concern
has a primary `location.path` in the selected changed files/range. Global
cleanup, archive, hotspot, and topology observations whose primary location is
outside that range may remain available as labelled context, `signals[]`, or
artifacts, but should not be indistinguishable from selected-scope top concerns.
The complete generated concern artifact remains the place for all generated
observations.

Incremental summaries expose scope hygiene counts:

- `scoped_concern_total`: generated selected-scope concern count.
- `global_context_concern_total`: generated global-context concern count.
- `displayed_scoped_concern_total`: selected-scope concerns displayed in
  top-level `concerns[]`.
- `displayed_global_context_concern_total`: global-context concerns displayed
  in top-level `concerns[]`.

`signals[]` 统一结构：

```json
{
  "kind": "cleanup|hotspot|topology|...",
  "summary": "",
  "metrics": {}
}
```

`risk_context` signal 的 `metrics` 使用 input counts 和 `by_factor` counts 表示外部事实覆盖面和实际 enrichment。字段可包含 `input_file_total`、`coverage_file_total`、`churn_file_total`、`test_map_file_total`、`changed_test_total`、`complexity_file_total`、`public_api_file_total`、`recurrence_file_total`、`enriched_concern_total` 和 `by_factor`。`by_factor` 可包含 `low_coverage`、`high_churn`、`missing_related_tests`、`high_complexity`、`public_api` 和 `recurring_history`。这些 metrics 只解释 risk facts 的附加情况，不是健康分。

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

成功 code-review 会把 payload guard 前的完整 generated concerns 写到 `.architec/code-review-concerns.json`，top-level `artifacts.code_review_concerns_json` 记录路径。写入失败对 `OSError` fail-open，并记录 `artifacts.code_review_concerns_error`。

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
