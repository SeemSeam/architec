# 4-6 周落地路线

落地路线分两条并行线：

- 主线：完成产品退位和四个建议型命令的最小闭环。
- 深化线：提升审查证据质量，先做少量高价值信号。

## Current Plan State

Done:

- 产品定位已收敛为 advisory-only，见 [positioning.md](positioning.md) 和 [decisions/001-advisory-only.md](decisions/001-advisory-only.md)。
- 公开命令已收敛为 `plan-review`、`code-review`、`fix-advice`、`status`，见 [commands.md](commands.md)。
- 方案目录已拆成 plan tree：根部骨架、`topics/`、`decisions/`、`open-questions.md`。
- 第一批核心决策已记录到 [decisions/](decisions/)。
- `plan-tree` skill 已补充状态维护、一致性检查和下一步记录规则。
- 当前方案已按 `plan-tree` 做过一次结构一致性维护，命令、topic、decision 链接关系可对齐。
- `plan-review` 最小 JSON 契约入口已由 agent4 实现，并经 agent3 审核通过。
- `plan-review` 第一小步收尾加固已由 agent4 实现，并经 agent3 审核通过。
- `code-review --full` 骨架和 cleanup file-level concern 已由 agent4 实现，并经 agent3 审核通过。
- `code-review --full` hotspot / topology file-level concern 下沉已由 agent4 实现，并经 agent3 审核通过。
- `code-review --diff` 最小骨架已由 agent4 实现，并经 agent3 审核通过。
- `code-review --since <ref>` 最小骨架已由 agent4 实现，并经 agent3 审核通过；code-review 三模式骨架收口完成。
- 旧 analysis 入口迁移影响面已由 agent4 完成零代码调研，并经 agent3 审核通过。
- 顶层 full/diff 入口路由到 code-review 底层的产品决策已记录，见 [decisions/006-top-level-code-review-routing.md](decisions/006-top-level-code-review-routing.md)。
- 顶层 `archi .` / `archi --diff .` 内部路由切换已由 agent4 实现，并经 agent3 审核通过。
- `--goal` 退位路径已记录，见 [decisions/007-goal-deprecation.md](decisions/007-goal-deprecation.md)。
- `--goal` deprecated 标记和 stderr warning 已由 agent4 实现，并经 agent3 审核通过。
- `--goal` 软切为迁移错误已由 agent4 实现，并经 agent3 审核通过。
- `--goal` parser 已由 agent4 移除。
- release notes、README 和 usage manual 的 advisory-review 迁移说明已由 agent4 完成，并经 agent3 审核通过。
- 工作区归属已确认：`self_manage.py` / `test_self_manage.py` 的无关改动已清出，剩余改动集中在 advisory-review 迁移范围内。
- `--goal` 软切后的不可达 `_analysis_result` 和 `_run_command` goal 分支已由 agent4 清理，并经 agent3 审核通过。
- `code-review` 输出契约决策已记录，见 [decisions/008-code-review-output-contract.md](decisions/008-code-review-output-contract.md)。
- `code-review` 输出契约已落到实现：`signals[]`、`evidence[]` 和 summary concern 计数语义已对齐 [topics/evidence-model.md](topics/evidence-model.md)。
- review event 生命周期已收敛为本地生成数据、默认 `.architec/`、10MB 分片策略，见 [decisions/009-review-event-lifecycle.md](decisions/009-review-event-lifecycle.md)。
- 旧命令迁移顺序已收敛为 warning、soft-cut、parser removal 三段策略，见 [decisions/010-legacy-command-migration-sequence.md](decisions/010-legacy-command-migration-sequence.md)。
- legacy 命令 deprecation warning 已落地；`autofix --apply` 已软切为迁移错误，不再执行自动落地。
- review event 生命周期 MVP 已落地：code-review 成功结果会追加本地 JSONL 事件，并按 10MB 阈值分片，并经 agent3 审核通过。
- advisory `status --trend/--snapshot` 与 auth `status --json` 的共存策略已记录，见 [decisions/011-status-command-coexistence.md](decisions/011-status-command-coexistence.md)。
- `status --trend` / `status --snapshot` 骨架已落地：显式 advisory 模式读取 review events，裸 `status` / `status --json` 保留 auth/session 行为，并经 agent3 审核通过。
- `fix-advice --for <review.json>` 骨架已落地：读取 CodeReviewResult concerns，输出非 patch、无 apply 的修复方向建议，并经 agent3 审核通过。
- `near_duplicate` v1 范围已收敛为全量审查里的 Python 函数/方法 AST 指纹重复，见 [decisions/012-near-duplicate-v1-scope.md](decisions/012-near-duplicate-v1-scope.md)。
- `near_duplicate` v1 已落地到 `code-review --full`：输出 `duplication` concern 和 `near_duplicate` signal，增量模式暂不启用，并经 agent3 审核通过。
- `archi autofix` 整体已软切为迁移错误；dry-run 和 `--apply` 均不再执行，替代入口为 `archi fix-advice --for <review.json>`，并经 agent3 审核通过。
- `archi gate` 整体已软切为迁移错误；不再执行 gate evaluation，替代入口为 advisory `archi code-review --diff .` 输出，并经 agent3 审核通过。
- `archi baseline` 整体已软切为迁移错误；不再捕获 legacy baseline artifacts，替代入口为 `archi status --snapshot`，并经 agent3 审核通过。
- legacy public API 调研已完成：`run_cleanup` / `run_autofix` / `run_gate` / `run_baseline` 当前无非 CLI 业务调用面，但仍有 exports、public tests 和文档残留。
- legacy public API 保留策略已记录，见 [decisions/013-legacy-public-api-retention.md](decisions/013-legacy-public-api-retention.md)。
- cleanup 子包 public API retire 决策已记录，见 [decisions/014-cleanup-subpackage-api-retire.md](decisions/014-cleanup-subpackage-api-retire.md)。
- README 和 usage manual 的 live usage 已收口：legacy maintenance commands 不再被描述为当前可执行 workflow。
- cleanup/archive 替代信号已补齐到 `code-review --full`：cleanup、archive、semantic_judge signals 覆盖旧 standalone cleanup 的候选、归档候选和语义复核观察。
- `archi cleanup` 整体已软切为迁移错误；不再执行 standalone cleanup scan，替代入口为 `archi code-review --full .` cleanup/archive signals，并经 agent3 审核通过。
- cleanup 子包 wrapper public API `run_cleanup` / `run_autofix` 已由 agent4 退役，并经 agent3 审核通过。
- root legacy public API `run_gate` / `run_baseline` retire 决策已记录，见 [decisions/015-root-legacy-public-api-retire.md](decisions/015-root-legacy-public-api-retire.md)。
- root legacy public API `run_gate` / `run_baseline` 已由 agent4 退役，并经 agent3 审核通过。
- legacy parser removal 决策已记录，见 [decisions/016-legacy-parser-removal.md](decisions/016-legacy-parser-removal.md)。
- legacy parser stubs `cleanup` / `autofix` / `baseline` / `gate` 已由 agent4 移除，并经 agent3 审核通过。
- `--goal` 已从顶层 parser 最终移除，并经 agent3 审核通过。
- Advisory-only 验收与文档定型：确认当前公开命令、历史文档和 release notes 都已对齐最终迁移状态。
- 裸 legacy token 行为已补友好错误提示：`archi cleanup` / `autofix` / `baseline` / `gate` 不再被当作 path 进入运行时链路。
- `docs/progressive-architectural-cleanup*` 已标记为 historical / archived，避免和当前 CLI 混淆。
- release notes 已补 final breaking changes checklist。
- skills / prompts 已扫描并更新，不再推荐 removed commands 或 retired public APIs。
- duplication advice + reference evidence 决策已记录，见 [decisions/017-duplication-advice-reference-evidence.md](decisions/017-duplication-advice-reference-evidence.md)。
- `near_duplicate` concern 已补可选 `references[]` 结构化 reference location，`fix-advice` 已为 `kind=duplication` 输出专用 advisory options。
- agent1 / agent4 / agent5 的 `archi-goal` 和 `archi-advice` skills 已同步到 `plan-review` / `code-review` 工作流，不再推荐 removed `archi --goal`。
- concern id 稳定性决策已记录，见 [decisions/018-concern-id-stability.md](decisions/018-concern-id-stability.md)；当前 code-review 生成的 concern id 已改为基于事实的 deterministic hash。
- `fix-advice --for <review.json>` 对缺失、无效或非 object review JSON 返回 CLI 错误；合法空 concerns 仍输出空 suggestions。
- 顶层 `archi .` / `archi --diff .` 的 human summary 已恢复 CodeReviewResult 下的 concern counts、signals 和 top concerns 摘要。
- status / review event 深化决策已记录，见 [decisions/019-status-event-semantics.md](decisions/019-status-event-semantics.md)。
- `status --trend` 已明确读取最近 100 条 review events，scores 来自最近 full code-review event，weakening components 使用 deterministic sort。
- `fix-advice` 已明确保持 consumer-only，不写 review event；code-review event 写入 `OSError` fail-open 已补测试。
- diff/since LLM preflight 精简决策已记录，见 [decisions/020-diff-preflight-policy.md](decisions/020-diff-preflight-policy.md)；advisory diff/since 不再要求 `architect_component_scoring` preflight。
- since range error 语义已记录，见 [decisions/021-since-range-error-semantics.md](decisions/021-since-range-error-semantics.md)；不可解析 ref/range 返回结构化 CodeReviewResult 降级对象。
- advisory-review open questions 已清空，剩余非封版方向移入 Deferred。
- `shadow_implementation` v1 范围已收敛为全量审查里的 Python 函数级跨文件相似实现，见 [decisions/022-shadow-implementation-v1-scope.md](decisions/022-shadow-implementation-v1-scope.md)。
- `shadow_implementation` v1 已落地到 `code-review --full`：输出 `shadow-implementation` concern 和 `shadow_implementation` signal，增量模式暂不启用。
- `shadow_implementation` class-level v1 已收敛并落地：全量审查可输出 Python 类级 `shadow-implementation` concern，见 [decisions/023-shadow-implementation-class-v1.md](decisions/023-shadow-implementation-class-v1.md)。
- `shadow_implementation` diff/since scope 已收敛：增量审查只报告 changed-file primary shadow concern，见 [decisions/024-shadow-implementation-diff-since-scope.md](decisions/024-shadow-implementation-diff-since-scope.md)。
- `fix-advice` 已为 `shadow-implementation` concern 增加专用 advisory options，消费 `references[].role: "existing_implementation"`，见 [decisions/025-shadow-implementation-fix-advice.md](decisions/025-shadow-implementation-fix-advice.md)。
- `near_duplicate` diff/since scope 已收敛：增量审查只报告 changed-file primary duplication concern，见 [decisions/026-near-duplicate-diff-since-scope.md](decisions/026-near-duplicate-diff-since-scope.md)。
- `code-review` top concerns 已改为 portfolio ranking：severity 优先，同 level 内优先展示不同 concern kind，见 [decisions/027-code-review-concern-ranking-diversity.md](decisions/027-code-review-concern-ranking-diversity.md)。
- `code-review` JSON 主体体量 guard 已落地：记录 `summary.payload_bytes`，并对过长展示字段写入 truncation metadata，见 [decisions/028-code-review-json-payload-budget.md](decisions/028-code-review-json-payload-budget.md)。
- `code-review` 完整 generated concerns artifact 已落地：成功路径写 `.architec/code-review-concerns.json`，见 [decisions/029-code-review-full-concerns-artifact.md](decisions/029-code-review-full-concerns-artifact.md)。
- `fix-advice --review <review.json>` 已成为推荐入口，`--for` 保留为兼容别名，见 [decisions/030-fix-advice-review-flag.md](decisions/030-fix-advice-review-flag.md)。
- `shadow_implementation` file-level 已进入 internal dry-run calibration：当前只输出 helper metrics，不接入 CodeReviewResult，见 [decisions/031-shadow-implementation-file-dry-run.md](decisions/031-shadow-implementation-file-dry-run.md)。
- `shadow_implementation` file-level dry-run 已在当前仓库采样：根仓 top candidates 被 `.ccb` provider-state/plugin 副本主导，`src/architec` 无 module pair，因此 public signal 继续 deferred，见 [decisions/032-shadow-implementation-file-public-signal-deferred.md](decisions/032-shadow-implementation-file-public-signal-deferred.md)。
- AI signal scanners 已补 source/generated-state exclusion：`near_duplicate` 和 `shadow_implementation` 默认跳过 `.ccb`、release-flow-test、generated/vendor/test/cache 等目录，见 [decisions/033-ai-signal-source-scope-exclusions.md](decisions/033-ai-signal-source-scope-exclusions.md)。
- 公开 advisory 命令 empty/degraded 文案已标准化：no-finding、no-events、合法空 suggestions 和 unable-to-analyze 输入降级保持中性表达，见 [decisions/034-advisory-empty-state-wording.md](decisions/034-advisory-empty-state-wording.md)。
- 长期架构稳定性下一阶段已收敛为 architecture contracts、plan/diff consistency 和 test/churn risk fusion，见 [topics/architecture-stability.md](topics/architecture-stability.md) 和 [decisions/035-architecture-stability-next-priorities.md](decisions/035-architecture-stability-next-priorities.md)。
- architecture contracts v1 已落地：`.architecture-rules.toml` 可声明 changed-file-scoped dependency restrictions，`code-review --diff/--since` 输出 `architecture-contract` concerns，见 [decisions/036-architecture-contracts-v1.md](decisions/036-architecture-contracts-v1.md)。
- plan/diff consistency v1 已落地：`code-review --diff/--since --plan-review <plan.json>` 可将 saved plan-review touchpoints 与 changed files 对齐，输出 `plan-diff-consistency` observations，见 [decisions/037-plan-diff-consistency-v1.md](decisions/037-plan-diff-consistency-v1.md)。
- `fix-advice` 已为 `architecture-contract` concern 增加专用边界导向 advisory options，见 [decisions/038-architecture-contract-fix-advice.md](decisions/038-architecture-contract-fix-advice.md)。
- risk context fusion v1 已落地：`code-review --risk-context <risk.json>` 可读取外部 coverage/churn/test-map facts，并附加到已有 concerns，见 [decisions/039-risk-context-fusion-v1.md](decisions/039-risk-context-fusion-v1.md)。
- plan/diff consistency import-edge expectation 已落地：`understood_plan.dependencies[]` 的 structured import 期望会与 selected changed Python files 的 imports 对齐，见 [decisions/040-plan-diff-import-edge-expectations.md](decisions/040-plan-diff-import-edge-expectations.md)。
- Hippocampus dogfood 审查已记录：full review 证明 shadow / duplication advice 有可用信号，diff review 暴露全局 cleanup/hotspot/topology 占据增量 top concerns 的 scope hygiene 问题，见 [topics/hippocampus-dogfood-audit-2026-05-14.md](topics/hippocampus-dogfood-audit-2026-05-14.md)。
- diff/since review scope hygiene 已落地：增量 top concern portfolio 优先展示 changed-file-scoped observations，全局 cleanup/hotspot/topology context 分离或明确标注，并输出 scoped/global summary counts，见 [decisions/041-diff-since-scope-hygiene.md](decisions/041-diff-since-scope-hygiene.md)。
- `near_duplicate` thin wrapper/facade boilerplate 抑制已落地：委托目标不同的薄 wrapper 不再作为低价值 duplication concern 输出，见 [decisions/042-near-duplicate-thin-wrapper-suppression.md](decisions/042-near-duplicate-thin-wrapper-suppression.md)。
- `shadow_implementation` role taxonomy precision 已落地：renderer 与 assembler/support/budget/context 等 intentional split-role pairs 被抑制，same-role 和 parser-helper candidates 仍可报告，见 [decisions/043-shadow-implementation-role-taxonomy.md](decisions/043-shadow-implementation-role-taxonomy.md)。
- risk context enrichment 已落地：`--risk-context` 接受可选 `complexity_by_file`、`public_api_files` 和 `historical_recurrence_by_file`，并把这些 facts 附加到已有 concerns，见 [decisions/044-risk-context-enrichment.md](decisions/044-risk-context-enrichment.md)。
- plan/diff consistency expected tests v1 已落地：`code-review --diff/--since --plan-review` 读取 saved plan-review JSON 中显式 structured expected-test entries，缺失 selected-diff test touchpoints 时输出 advisory observations，见 [decisions/045-plan-diff-expected-tests.md](decisions/045-plan-diff-expected-tests.md)。

In Progress:

- 无。

Next:

- 继续深化 test/churn risk fusion 的 richer external report formats。
- 评估 plan/diff consistency 的下一层语义：public API migration notes 或 dependency alternatives。

Deferred:

- `shadow_implementation` file-level 正式接入 CodeReviewResult（等待真实 positive fixtures 和 variant taxonomy）。
- 多语言支持。
- 自建运行时信号采集。
- 用户自定义脚本化规则平台。

## 第 1 周：产品退位

主线：

- 从帮助文档和 README 中移除 `goal`、`advice`、`gate`、`autofix --apply` 的主入口描述。
- 明确 `architec` 只做分析和建议。
- 给出旧命令到新命令的迁移表。
- 更新 skills 命名方向，避免继续使用 `archi-goal`、`archi-advice` 这样的规划型词汇。
- 将无 goal 的顶层 full/diff 入口内部路由到 `code-review` 底层。
- 将 `--goal` 标记 deprecated，并提示迁移到 `plan-review`。
- 将 `--goal` 软切为迁移错误，不再执行规划型旧 analysis。
- 从 parser 中移除 `--goal`。
- 发布说明已覆盖顶层 `--out` 切换到 CodeReviewResult、`--goal` parser removal 和新 `plan-review` / `code-review` 入口。

深化线：

- 定义统一 concern 数据结构。
- 明确 concern 不包含结构化修复建议。

验收：

- 用户只看 README 就能理解 `architec` 不负责规划、不做门禁、不自动改代码。

## 第 2 周：收敛 code-review

主线：

- 实现 `code-review --full`。（骨架和 cleanup / hotspot / topology file-level concern 已通过审核）
- 实现 `code-review --diff`。（最小骨架已通过审核）
- 实现 `code-review --since <ref>`。（最小骨架已通过审核）
- 统一 JSON、Markdown、HTML 输出结构。
- 将 cleanup/archive 作为 signals 呈现。
- 增量审查严格只报告本次变化。
- 统一 `signals[]`、`evidence[]` 和 summary concern 计数语义。

深化线：

- 将现有 hotspot、cleanup、topology concern 下沉到文件级 evidence。
- 增量审查开始输出本次变化的 concern 排序。

验收：

- 现有 `archi .` 和 `archi --diff .` 的核心信息都能从 `code-review` 获取。

## 第 3-4 周：补 plan-review

主线：

- 定义 plan MD 推荐模板。
- 实现 Markdown 提取：intent、changes、dependencies、notes。（最小版本已通过审核）
- 输出 understood plan，暴露解析结果。（最小版本已通过审核）
- 输出 `concerns` 和 `suggested_adjustments` 两层结构。（最小版本已通过审核）
- 生成 plan fingerprint。（最小版本已通过审核；稳定性策略已文档化）
- 支持 code-review 增量模式读取 plan fingerprint 做一致性观察。

深化线：

- 加入 plan 缺漏检查清单：测试、依赖、public API、迁移说明。
- plan-review 不输出量化分数预测，只输出可能影响的维度名单和理由。

验收：

- 一份方案 MD 可以得到清晰的审查建议。
- code-review 可以提示实际改动是否偏离方案触达范围。

## 第 5 周：补 fix-advice

主线：

- 支持读取 review JSON。
- 按文件、组件、信号类别聚焦建议。
- 输出多种可考虑修复方向。
- 移除自动 apply 概念。

深化线：

- 实现第一批 AI 特有信号中的 `near_duplicate`。
- `shadow_implementation` v1 已作为封版后深化项落地；增量范围控制和专用 fix-advice 已补齐，file-level 当前仅做 dry-run calibration。
- `near_duplicate` 已扩展到 diff/since changed-file scope，仍保持 exact normalized AST fingerprint。

验收：

- 任意 review 结果都可以生成独立的修复建议报告。

## 第 6 周：补 status

主线：

- 实现 `status --snapshot`。
- 实现 `status --trend`。
- 每次 review 可追加摘要事件到 `.architec/review-events.jsonl`。
- 趋势视图展示维度变化和显著变动来源。

深化线：

- 增量审查可引用历史事件，说明某维度变化是否属于连续趋势。
- 输出体量控制：JSON 主体不含 artifacts 目标小于 20KB，超出时截断明细并保留 top concerns。

验收：

- 用户可以看到项目一段时间内是否在结构上恶化或改善。

## 降级顺序

如果工期吃紧，优先保主线。深化线按以下顺序降级：

- 先推迟 `shadow_implementation` 的 file-level 深化。
- 再推迟趋势归因细化。
- 最后推迟 plan fingerprint 的精细一致性观察。

不能推迟的是产品退位、`code-review` 收敛和 `plan-review` 基本输出。

## 成功标准

产品层成功标准：

- 推荐模板格式的 plan MD 中，intent、changes、dependencies 三段提取成功率达到 90% 以上。
- `code-review --diff` 只输出本次新增或恶化的 concern，不混入历史旧账。
- `fix-advice` 输出不包含 patch、不包含 `apply` 字段、不包含执行顺序承诺。
- `status --snapshot` 能写入快照，`status --trend` 在无历史时能稳定输出空趋势说明。
- README 和 `archi --help` 不包含 `pass`、`fail`、`block`、`must fix`、`required before merge` 这类裁决语义。

工程层成功标准：

- 新命令覆盖旧 full/diff 的核心信息。
- JSON 输出符合固定 schema，并能通过 schema 校验。
- 主 JSON 输出不含 artifacts 的目标大小小于 20KB，超出部分进入 artifacts。
- Markdown/HTML 输出保持适合人类阅读。
- 现有测试迁移到新命令语义。
- `PYTHONPATH=src python3 -m pytest -q` 通过。
