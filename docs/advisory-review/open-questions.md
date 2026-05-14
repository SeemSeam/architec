# 未决项

本文件记录封版时仍开放或延后的讨论项。

当前 advisory-review 迁移封版范围内无未决项。

以下为未决设计点或已转入 roadmap Deferred 的方向，不作为当前封版阻塞项：

- plan/diff consistency 的路径级输入来源已由 [037-plan-diff-consistency-v1.md](decisions/037-plan-diff-consistency-v1.md) 决策为读取完整 saved plan-review JSON；structured dependency import expectations 已由 [040-plan-diff-import-edge-expectations.md](decisions/040-plan-diff-import-edge-expectations.md) 收敛；explicit expected-test entries 已由 [045-plan-diff-expected-tests.md](decisions/045-plan-diff-expected-tests.md) 决策；dependency alternatives 已由 [046-plan-diff-dependency-alternatives.md](decisions/046-plan-diff-dependency-alternatives.md) 决策；public API migration touchpoints 已由 [047-plan-diff-public-api-migrations.md](decisions/047-plan-diff-public-api-migrations.md) 决策。更细的 semantic intent matching 仍未决策。
- Hippocampus dogfood re-run after Decisions 041-047 confirmed diff/since scope hygiene. The `near_duplicate` same-file variant-family grouping question is now decided by [048-near-duplicate-variant-family-grouping.md](decisions/048-near-duplicate-variant-family-grouping.md). Remaining detector/advice precision questions: whether `shadow_implementation` mapper role taxonomy should split color/rename/shape mapping responsibilities, and whether duplication `fix-advice` should recognize legacy/compat intent more explicitly.
- python-dotenv dogfood full-review context calibration v1 is now decided by [049-full-review-context-calibration.md](decisions/049-full-review-context-calibration.md). Broader calibration thresholds for larger, multi-package, or fast-growing repositories remain empirical follow-up rather than current migration blockers.
- risk context fusion v1 的外部报告格式已由 [039-risk-context-fusion-v1.md](decisions/039-risk-context-fusion-v1.md) 决策为 optional coverage/churn/test-map JSON；complexity/public API/historical recurrence enrichment 已由 [044-risk-context-enrichment.md](decisions/044-risk-context-enrichment.md) 决策。更丰富的外部报告格式和跨事件历史解释仍未决策。
- `shadow_implementation` file-level 是否正式接入 CodeReviewResult 已决策为继续 deferred。source/generated-state exclusion 已由 [033-ai-signal-source-scope-exclusions.md](decisions/033-ai-signal-source-scope-exclusions.md) 补齐；重新评估前仍需要真实 positive fixtures 和更清晰的 provider/plugin variant taxonomy，见 [decisions/032-shadow-implementation-file-public-signal-deferred.md](decisions/032-shadow-implementation-file-public-signal-deferred.md)。
- TypeScript/Go 多语言调研。
