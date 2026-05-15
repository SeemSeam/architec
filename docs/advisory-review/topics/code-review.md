# code-review 代码审查

`code-review` 审查代码结构风险。它不输出 pass/fail，不做门禁，不自动调用修复建议。

## 输入

```bash
archi code-review --full .
archi code-review --diff .
archi code-review --diff --plan-review <plan.json> .
archi code-review --since <ref> .
archi code-review --diff --risk-context <risk.json> .
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

Full-review context calibration v1 见 [Decision 049](../decisions/049-full-review-context-calibration.md)：full review 仍保留 cleanup、archive、semantic judge、hotspot 和 topology signals，但默认 top concerns 需要避免低价值展示噪声。Active changelog/release notes stale-doc observations 应从 top-level concerns 抑制或降级；cleanup/archive 对同一路径的 retention 观察不应同时占据 top concern slots；当 `needs_folder_management=false` 且 flat file count 较小时，topology boundary 观察应保留为 signal context，而不是默认 top-level boundary concern。Raw signals 和 generated artifacts 仍可保留完整上下文。

Semantic keep-active display calibration 见 [Decision 061](../decisions/061-semantic-keep-active-display-calibration.md)：full review 中，如果 semantic cleanup judge 以 `decision: "keep_active"` 明确判定同一路径仍是 active surface，则该路径的 `stale_doc` cleanup/archive concern 不进入默认 top concerns。完整 generated concerns artifact、cleanup/archive signals 和 semantic judge artifacts 仍保留原始上下文。

Semantic review display reinforcement 见 [Decision 062](../decisions/062-semantic-review-display-reinforcement.md)：full review 中，如果 semantic cleanup judge 以 `decision: "review"` 明确要求人工复核同一路径，则匹配的 cleanup/archive concern 会增加 `semantic_judge.decision=review` evidence，并把展示 confidence floor 提升到 `0.76`。这不会创建新 concern，也不影响非 cleanup/archive signals。

Semantic archive/retire display reinforcement 见 [Decision 064](../decisions/064-semantic-archive-retire-display-reinforcement.md)：full review 中，如果 semantic cleanup judge 以 `decision: "archive_first"` 或 `decision: "retire_now"` 明确强化同一路径的 archive/retire 语义，则匹配的 cleanup/archive concern 会增加对应 `semantic_judge.decision=...` evidence，并提高展示 confidence floor。它不覆盖 `keep_active` 降级，不影响 non-ok semantic judge，不从 semantic judge 输出创建新 concern，也不改变 generated-concerns artifact contract 或 fix-advice 行为。

全量审查中的 AI/vibe coding 信号当前包括：

- `near_duplicate`：规范化 AST 指纹重复，输出 `duplication` concern，并通过 `references[]` 标出 reference implementation。
- `shadow_implementation`：函数级和类级跨文件相似实现，输出 `shadow-implementation` concern，并通过 `references[]` 标出 `existing_implementation`。

`near_duplicate` 仍以 exact normalized AST fingerprint 为基础，但会抑制 thin wrapper/facade boilerplate：如果两个薄 wrapper 只是形状相同且委托到不同 target，它们不作为高价值 duplication concern 输出。variant-family grouping v1 见 [Decision 048](../decisions/048-near-duplicate-variant-family-grouping.md)：same-file phase/cache/prompt-builder exact duplicates 可以被合并为一个 advisory duplication observation，或在 top concern 展示中限流。Mature-library calibration v1 见 [Decision 054](../decisions/054-ai-drift-mature-library-calibration.md)：AI drift scanners 默认排除 `benchmark` / `benchmarks` 路径段，`near_duplicate` 对同文件 explicit paired API variants 做保守 suppression。Member variant-family grouping v1 见 [Decision 059](../decisions/059-near-duplicate-member-variant-families.md)：同文件 class/member API families 会被合并为 grouped duplication observations，prefixed paired API variants 进入 discovery lane。重复的实质逻辑、cross-file duplicates 和委托到同一 target 的 wrapper 仍可被报告。

`shadow_implementation` 仍以 role overlap、AST similarity、signature/class API similarity、name overlap 和 no reuse edge 为基础，但会抑制清晰的 renderer versus assembler/support/budget/context split-role pairs。Mapper taxonomy v1 见 [Decision 050](../decisions/050-shadow-mapper-taxonomy.md)：visualization color/palette/style/tier/role mapping 与 rename/move/old/new/diff migration mapping 的明显跨域 pairs 会被抑制。Parser subdomain taxonomy v1 见 [Decision 057](../decisions/057-shadow-parser-subdomain-taxonomy.md)：runtime/platform parser、local-version parser 与 version grammar parser 的明显跨域 pairs 会被抑制；same-domain mapper/parser、same-role candidates 和 parser-helper pairs 仍可报告；scope、`references[].role: "existing_implementation"`、`concern_id` 和 `fix-advice` 语义不变。

`near_duplicate` 和 `shadow_implementation` 在增量模式中只报告 `location.path` 位于 changed files 的 concern，`references[]` 可以指向未变更的 existing/reference implementation。`near_duplicate` 不因为 reference path changed 而报告历史旧账。

File/module-level `shadow_implementation` 目前只保留为 internal dry-run calibration helper。它不会被 `code-review` 调用，不会产生 `signals[]`，也不会产生 `location.symbol_kind: "module"` 的 `shadow-implementation` concern。

Advisory recall discovery lane 见 [Decision 055](../decisions/055-advisory-recall-discovery-lane.md)。Discovery lane v1 见 [Decision 056](../decisions/056-advisory-discovery-lane-v1.md)：suppressed `near_duplicate` candidates 和 module-level shadow dry-run candidates 会进入 `.architec/code-review-discovery.json` 与 `advisory_discovery` signal metrics；默认 `concerns[]`、`evidence[]` 和 human summary 仍保持高精度，不因 discovery candidates 自动膨胀。

Architecture contracts v1 在增量模式中读取 `.architecture-rules.toml` 的 `architecture_contracts` 规则，只检查 changed Python files。匹配 `source_glob` 且导入 `restricted_imports` 的文件会产生 `kind: "architecture-contract"` concern；没有 contract config 时不输出 contract signal 或 concern。

示例：

```toml
[[archi.architecture_contracts]]
id = "api-no-storage"
source_glob = "src/api/**"
owner = "api-platform"
restricted_imports = ["app.storage"]
note = "Use the service facade."
```

Plan/diff consistency v1 在增量模式中可选读取已保存的 `plan-review` JSON：

```bash
archi plan-review plan.md --out plan.json
archi code-review --diff --plan-review plan.json .
```

它比较 `understood_plan.changes[].path` 与本次 `change_analysis.changed_files`，对计划外 changed file 或计划中未触达路径输出 `kind: "plan-diff-consistency"` concern。它还读取 structured `understood_plan.dependencies[]` import expectations；如果 selected changed Python files 中没有观察到计划的 import edge，会输出 `plan_diff_consistency.observation=planned_import_not_observed`。Dependency alternatives v1 见 [Decision 046](../decisions/046-plan-diff-dependency-alternatives.md)：structured dependency entries 可以列出 acceptable import alternatives，source scope 内 selected changed Python files import 任一 listed module 即满足；若全部未观察到，输出 advisory plan-diff observation。Expected tests v1 见 [Decision 045](../decisions/045-plan-diff-expected-tests.md)：只读取 saved plan-review JSON 中显式 structured expected-test entries；如果 expected test file 没有出现在 selected changed files 中，输出 advisory `plan_diff_consistency.observation=planned_test_not_observed`。Public API migrations v1 见 [Decision 047](../decisions/047-plan-diff-public-api-migrations.md)：只读取 explicit structured public API migration touchpoints；缺失 selected-diff migration touchpoint 时输出 advisory plan-diff observation。Semantic intent matching v1 见 [Decision 053](../decisions/053-plan-diff-semantic-intent-matching.md)：只读取 `understood_plan.intent_checks[]` 和 `understood_plan.semantic_intents[]` 中的 dict entries，用 deterministic text-term matching 检查 scoped selected changed text files 的 required all terms、required any terms 和 forbidden terms；缺失 required terms 输出 `plan_diff_consistency.observation=planned_intent_terms_not_observed`，出现 forbidden terms 输出 `plan_diff_consistency.observation=planned_intent_conflict_observed`。任意 string/prose test、dependency、migration 或 intent note 只作为上下文，不作为 requirement；`understood_plan.intent` 和 `changes[].intent` 自然语言不会被用来猜需求。full review 不运行这些 plan/diff checks；since bad-ref degraded result 不读取 plan 或运行 scanner。这些观察只表达实现与已审查计划的显式结构化期望之间的偏离，不判断计划或代码哪一方正确，也不证明需求正确性。

Risk context fusion v1 可选读取外部 JSON：

```bash
archi code-review --diff --risk-context risk.json .
```

`risk.json` 可以包含 `coverage_by_file`、`churn_by_file`、`test_files_by_source`、`changed_tests`，以及 [Decision 044](../decisions/044-risk-context-enrichment.md) 接受的 `complexity_by_file`、`public_api_files`、`historical_recurrence_by_file`。External report formats v1 见 [Decision 052](../decisions/052-risk-context-external-report-formats.md)：同一个 JSON 还可以包含 coverage.py-style `files[*].summary.percent_covered`、radon-like complexity maps 和 simple churn aliases，归一化为既有 `risk_context` facts；显式 first-class 字段优先于 derived report values。`code-review` 只把这些外部事实附加到已有 concerns，并输出 `risk_context` signal；它不执行测试、不生成 coverage、不计算 complexity、不挖掘历史 recurrence、不计算新的健康分。

Full review reliability v1 见 [Decision 058](../decisions/058-full-code-review-static-degradation.md)：当 full code-review 无法使用 Hippo bundle 或 backend LLM path 时，CLI 会返回明确标记的 static CodeReviewResult，而不是直接中断 dogfood。该结果使用 `summary.analysis_mode=static`、`summary.reason` 和 `artifacts.code_review_static_reason` 标记降级原因，并保留 deterministic `near_duplicate`、`shadow_implementation` 和 advisory discovery signals。diff/since review 不走该降级路径，因为 selected-change 语义依赖完整 diff analysis。

Hippo manifest source-scope alignment 见 [Decision 060](../decisions/060-hippo-manifest-source-scope-alignment.md)：bundle validation 会把 Hippo `file-manifest.json` 明确标记为 architecture source 的路径纳入当前 source mtimes，即使 Architec 本地 path policy 会把 `docs/conf.py` 或 `docs/Makefile` 归为 docs。这样 fresh Hippo bundle 不会因为 producer/validator source scope 不一致而误退化到 static review。

## Dogfood Follow-Up

2026-05-14 的 Hippocampus dogfood 审查显示：full review 能产生可用的 duplicate / shadow advice，但 diff review 的 top concerns 会被与 selected diff 无关的 global cleanup、hotspot、topology concerns 占据。diff/since scope hygiene 已按 [../decisions/041-diff-since-scope-hygiene.md](../decisions/041-diff-since-scope-hygiene.md) 落地：

- changed-file-scoped observations 应优先进入增量 top concerns；
- global cleanup/hotspot/topology 应作为 labelled context、signals 或 artifact，而不是伪装成 selected diff 的主要 concern；
- summary 使用 `scoped_concern_total`、`global_context_concern_total`、`displayed_scoped_concern_total` 和 `displayed_global_context_concern_total` 表达 scoped/global 生成量和展示量。

这不改变 advisory-only 边界。Architec 仍然只提供 drift、duplication、boundary 和 trend feedback，不保证 mainline correctness。

这次 dogfood 是 Architec 对自身审查能力的自评信号，不是对 Hippocampus 项目的审计结论。release notes 和 roadmap 应把相关发现表述为 Architec 行为观察，而不是 Hippocampus 代码问题。

同一轮 dogfood 还暴露了 shadow role taxonomy precision follow-up：renderer 与 assembler/support/budget/context helper 可能共享 mapper token 和 AST shape，但职责是 intentional split。该点已由 [../decisions/043-shadow-implementation-role-taxonomy.md](../decisions/043-shadow-implementation-role-taxonomy.md) 收敛；后续 `_module_color_map` versus `module_rename_map` 暴露的 mapper color/rename subdomain split 已由 [../decisions/050-shadow-mapper-taxonomy.md](../decisions/050-shadow-mapper-taxonomy.md) 收敛。multi-repo dogfood 暴露的 parser subdomain split 已由 [../decisions/057-shadow-parser-subdomain-taxonomy.md](../decisions/057-shadow-parser-subdomain-taxonomy.md) 收敛。parser-helper、same-domain mapper/parser 和 same-role shadow candidates 仍保留。

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

Diff/since scope hygiene 的展示边界见 [../decisions/041-diff-since-scope-hygiene.md](../decisions/041-diff-since-scope-hygiene.md)。增量 `concerns[]` 应优先展示 selected changed-file concerns；全局 cleanup、archive、hotspot 和 topology 观察可以继续作为 labelled context、signals 或 artifact 留存，但不能让用户误读为 selected diff 的主要问题。

## 空/降级输出

- 如果增量审查没有发现新增或恶化的问题，输出空 `findings` 和明确摘要：`No new architecture concerns were identified in the selected diff.`
- `--since <ref>` 的合法空结果使用 `No new architecture concerns were identified in the selected since range.`
- 如果 `--since <ref>` 的引用或 range 不可解析，输出结构化 CodeReviewResult 降级对象，不回退到全量审查或无关工作树 diff。
- since range 降级 headline 使用 `Unable to analyze the requested since range.`，并在 `summary.reason` 中说明 requested range could not be resolved。
- 如果关联方案指纹不可读取，只跳过方案一致性观察，保留普通 code-review 输出。

## LLM Preflight

advisory code-review 的 full、diff、since 模式使用同一组基础 LLM preflight checks。diff/since 不额外要求 `architect_component_scoring` preflight，以保持增量反馈轻量；底层分析仍可在运行时复用 component scoring 能力。

## 排序和边界

concern 排序使用 portfolio ranking。排序先按 severity level 分层，低 level 不会只因多样性排到高 level 前面；同一 level 内按 confidence、是否有 path、path 做确定性基础排序，并在第一轮展示中对每个 kind 使用 soft cap，优先让 top-N 覆盖不同风险维度。可修复性属于 `fix-advice` 范畴，不作为 `code-review` 排序因子。

`code-review --full` 展示当前快照的薄弱模块；`status` 展示薄弱模块如何随时间变化。

## 输出计数

`concerns[]` 默认只展示 top concerns portfolio，不代表唯一完整真相。`summary.concern_total` 记录截断前总数，`summary.top_concern_total` 记录本次展示数量，`summary.concern_limit` 记录 top-N 上限。

Discovery lane candidates 不计入 `summary.concern_total`，除非它们后续按 [Decision 055](../decisions/055-advisory-recall-discovery-lane.md) 的强化条件提升为 primary concern。Discovery 信息通过 artifact 或明确命名的 signal metrics 暴露，避免和默认 top concerns 混淆。

在 diff/since 模式下，summary 区分 selected-scope 与 global-context 计数：`scoped_concern_total` 记录 generated selected-scope concern count，`global_context_concern_total` 记录 generated global-context concern count，`displayed_scoped_concern_total` 记录 top-level `concerns[]` 中展示的 scoped count，`displayed_global_context_concern_total` 记录 top-level `concerns[]` 中展示的 global context count。这些字段让 agent 和人类读者看出 top-level concerns 是否来自 selected change。

Incremental cleanup/archive display de-dupe 见 [Decision 065](../decisions/065-incremental-cleanup-archive-display-dedupe.md)：diff/since selected-scope 中同一 `location.path` 和 category 的 cleanup/archive observations 在默认 `concerns[]` 中只占一个 top concern slot；完整 generated concerns artifact 仍保留两条原始 observation。

`signals[]` 只用 `kind`、`summary`、`metrics` 三个通用字段；信号专属数据放进 `metrics`，避免每类 signal 发明不同顶层字段。

`concern_id` 是基于事实生成的引用标识，不代表展示顺序。当前生成格式为 `code-review:<kind>:<hash>`；hash 输入来自 mapper source、primary location、evidence，以及 duplication reference/fingerprint 等事实。

主 JSON payload 使用保守体量 guard。`summary.payload_bytes` 记录不含 artifacts 的 compact JSON 估算；过长的 concern evidence、references、blast radius 或一层 signal metric map 会在展示层截断，并通过 `artifacts.payload_truncation` 记录。该 guard 不改变 detector、ranking、`concern_id` 或 `concern_total`。

成功的 code-review 会写出完整 generated concerns artifact：`.architec/code-review-concerns.json`，并在 top-level `artifacts.code_review_concerns_json` 中记录路径。该 artifact 保存 payload guard 前的完整 generated concerns；写入失败对 `OSError` fail-open，并记录 `artifacts.code_review_concerns_error`。
