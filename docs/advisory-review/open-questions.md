# 未决项

本文件记录封版时仍开放或延后的讨论项。

当前 advisory-review 迁移封版范围内无未决项。

以下方向已转入 roadmap Deferred，不作为当前封版阻塞项：

- architecture contracts 的规则格式和配置位置尚未决策。
- plan/diff consistency 的输入来源尚未决策：只读 plan fingerprint，还是读取完整 plan-review JSON。
- test/churn risk fusion 的外部报告格式尚未决策。
- `shadow_implementation` file-level 是否正式接入 CodeReviewResult 已决策为继续 deferred。source/generated-state exclusion 已由 [033-ai-signal-source-scope-exclusions.md](decisions/033-ai-signal-source-scope-exclusions.md) 补齐；重新评估前仍需要真实 positive fixtures 和更清晰的 provider/plugin variant taxonomy，见 [decisions/032-shadow-implementation-file-public-signal-deferred.md](decisions/032-shadow-implementation-file-public-signal-deferred.md)。
- TypeScript/Go 多语言调研。
