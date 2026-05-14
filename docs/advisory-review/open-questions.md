# 未决项

本文件记录封版时仍开放或延后的讨论项。

当前 advisory-review 迁移封版范围内无未决项。

以下为未决设计点或已转入 roadmap Deferred 的方向，不作为当前封版阻塞项：

- plan/diff consistency 的路径级输入来源已由 [037-plan-diff-consistency-v1.md](decisions/037-plan-diff-consistency-v1.md) 决策为读取完整 saved plan-review JSON；更深的 import-edge expectation 仍未决策。
- risk context fusion v1 的外部报告格式已由 [039-risk-context-fusion-v1.md](decisions/039-risk-context-fusion-v1.md) 决策为 optional coverage/churn/test-map JSON；complexity/public API risk 和更深历史融合仍未决策。
- `shadow_implementation` file-level 是否正式接入 CodeReviewResult 已决策为继续 deferred。source/generated-state exclusion 已由 [033-ai-signal-source-scope-exclusions.md](decisions/033-ai-signal-source-scope-exclusions.md) 补齐；重新评估前仍需要真实 positive fixtures 和更清晰的 provider/plugin variant taxonomy，见 [decisions/032-shadow-implementation-file-public-signal-deferred.md](decisions/032-shadow-implementation-file-public-signal-deferred.md)。
- TypeScript/Go 多语言调研。
