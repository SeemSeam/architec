# architec advisory review 产品方案

> `architec` 只做建议型架构审查：不规划、不门禁、不自动落地。

## 核心决策

- 不做门禁，所有输出都是观察和建议。见 [001-advisory-only.md](decisions/001-advisory-only.md)。
- 不做规划，`goal` 公开入口退役。见 [002-drop-goal.md](decisions/002-drop-goal.md)。
- 不自动落地，`autofix --apply` 退役。见 [003-no-autofix-apply.md](decisions/003-no-autofix-apply.md)。
- 当前阶段只聚焦 Python 项目。见 [004-python-only.md](decisions/004-python-only.md)。
- `plan-review` 当前只审查单个方案 Markdown 文件。见 [005-single-plan-file.md](decisions/005-single-plan-file.md)。
- 顶层 `archi .` / `archi --diff .` 已路由到 `code-review` 底层。见 [006-top-level-code-review-routing.md](decisions/006-top-level-code-review-routing.md)。
- `--goal` 已从 parser 移除，替代入口是 `archi plan-review <plan.md>`。见 [007-goal-deprecation.md](decisions/007-goal-deprecation.md)。
- `code-review` 输出契约区分 top concerns、signals 和 evidence index。见 [008-code-review-output-contract.md](decisions/008-code-review-output-contract.md)。
- review 事件流是本地生成数据，默认写入 `.architec/` 并按 10MB 分片。见 [009-review-event-lifecycle.md](decisions/009-review-event-lifecycle.md)。
- 旧命令按 warning、soft-cut、parser removal 分阶段退位；`autofix --apply` 和 `gate` 优先处理。见 [010-legacy-command-migration-sequence.md](decisions/010-legacy-command-migration-sequence.md)。
- advisory `status --trend/--snapshot` 与既有 auth `status --json` 通过显式模式共存。见 [011-status-command-coexistence.md](decisions/011-status-command-coexistence.md)。
- `near_duplicate` v1 采用保守 Python AST 指纹，只在全量审查中输出。见 [012-near-duplicate-v1-scope.md](decisions/012-near-duplicate-v1-scope.md)。
- legacy CLI parsers 已移除，底层 legacy public API 已分阶段退役。见 [013-legacy-public-api-retention.md](decisions/013-legacy-public-api-retention.md)。
- cleanup 子包 wrapper API `run_cleanup` / `run_autofix` 已退役。见 [014-cleanup-subpackage-api-retire.md](decisions/014-cleanup-subpackage-api-retire.md)。
- root legacy public API `architec.run_gate` / `architec.run_baseline` 已退役。见 [015-root-legacy-public-api-retire.md](decisions/015-root-legacy-public-api-retire.md)。
- legacy parser stubs 和 `--goal` 已最终移除。见 [016-legacy-parser-removal.md](decisions/016-legacy-parser-removal.md)。
- duplication concern 使用可选结构化 reference evidence，`fix-advice` 为 duplication 输出专用建议。见 [017-duplication-advice-reference-evidence.md](decisions/017-duplication-advice-reference-evidence.md)。
- code-review concern id 使用基于事实的稳定标识，不表达排序位置。见 [018-concern-id-stability.md](decisions/018-concern-id-stability.md)。
- status trend 使用最近 100 条 review events，scores 来自最近 full code-review event；`fix-advice` 不写 event。见 [019-status-event-semantics.md](decisions/019-status-event-semantics.md)。
- advisory diff/since code-review 使用轻量 LLM preflight，不再要求 `architect_component_scoring`。见 [020-diff-preflight-policy.md](decisions/020-diff-preflight-policy.md)。
- `code-review --since <ref>` 对不可解析 range 返回结构化 CodeReviewResult 降级对象。见 [021-since-range-error-semantics.md](decisions/021-since-range-error-semantics.md)。
- `shadow_implementation` v1 采用保守 Python 函数级静态检测，只在全量审查中输出。见 [022-shadow-implementation-v1-scope.md](decisions/022-shadow-implementation-v1-scope.md)。
- `shadow_implementation` class-level v1 扩展到 Python 类级候选，仍只在全量审查中输出。见 [023-shadow-implementation-class-v1.md](decisions/023-shadow-implementation-class-v1.md)。
- `shadow_implementation` diff/since scope 只报告 changed-file primary concerns，引用可指向未变更实现。见 [024-shadow-implementation-diff-since-scope.md](decisions/024-shadow-implementation-diff-since-scope.md)。
- `fix-advice` 为 `shadow-implementation` concern 输出专用 advisory options，消费 `references[].role: "existing_implementation"`。见 [025-shadow-implementation-fix-advice.md](decisions/025-shadow-implementation-fix-advice.md)。
- `near_duplicate` diff/since scope 只报告 changed-file primary duplication concern，reference 可指向未变更实现。见 [026-near-duplicate-diff-since-scope.md](decisions/026-near-duplicate-diff-since-scope.md)。
- `code-review` top concerns 使用 portfolio ranking，在同一 severity 内优先展示不同 kind。见 [027-code-review-concern-ranking-diversity.md](decisions/027-code-review-concern-ranking-diversity.md)。
- `code-review` 主 JSON payload 使用保守体量 guard，记录 `summary.payload_bytes` 和可选 truncation metadata。见 [028-code-review-json-payload-budget.md](decisions/028-code-review-json-payload-budget.md)。

## 目录

根部文件是方案骨架：

| 文档 | 内容 |
| --- | --- |
| [positioning.md](positioning.md) | 产品定位、非目标、语言规则、与其他工具的边界 |
| [commands.md](commands.md) | 公开命令体系、模式矩阵、旧功能迁移 |
| [release-notes.md](release-notes.md) | advisory-review 迁移发布说明 |
| [roadmap.md](roadmap.md) | 4-6 周落地路线、主线与深化线 |
| [risks.md](risks.md) | 主要风险和缓解策略 |
| [open-questions.md](open-questions.md) | 封版时未决项状态 |

细则文件放在 `topics/`：

| 文档 | 内容 |
| --- | --- |
| [topics/plan-review.md](topics/plan-review.md) | 方案 Markdown 审查输入、输出、降级策略和深化方向 |
| [topics/code-review.md](topics/code-review.md) | 全量/增量代码审查语义、输出重点和边界 |
| [topics/fix-advice.md](topics/fix-advice.md) | 修复建议的输入输出和边界 |
| [topics/status.md](topics/status.md) | 快照、趋势和长期状态观察 |
| [topics/evidence-model.md](topics/evidence-model.md) | JSON 契约、concern 结构、输出体量、事件流生命周期 |
| [topics/review-shortcomings.md](topics/review-shortcomings.md) | 当前审查能力短板 |
| [topics/ai-signals.md](topics/ai-signals.md) | AI/vibe coding 特有坏味信号 |
| [topics/external-signals.md](topics/external-signals.md) | 历史、测试、依赖、运行时信号取舍 |

决策记录放在 [decisions/](decisions/)；只追加，不改写历史。

## 公开入口

```bash
archi plan-review <plan.md>
archi code-review --full .
archi code-review --diff .
archi code-review --since <ref> .
archi fix-advice --for <review.json>
archi status --trend
archi status --snapshot
```

## 能力迁移摘要

| 现有入口 | 新定位 |
| --- | --- |
| `archi .` | `archi code-review --full .` |
| `archi --diff .` | `archi code-review --diff .` |
| `archi --goal ...` | parser 已移除，迁移到 `archi plan-review <plan.md>` |
| `archi gate` | parser 已移除，不做门禁；迁移到 advisory `archi code-review --diff .` |
| `archi baseline` | parser 已移除，迁移到 `archi status --snapshot` |
| `archi cleanup` | parser 已移除，迁移到 `archi code-review --full .` cleanup/archive signals |
| `archi archive` | `code-review` signal |
| `archi autofix` | parser 已移除，迁移到 `archi fix-advice` |
| `archi autofix --apply` | parser 已移除，不提供自动修改 |

## 状态

active · updated 2026-05-13
