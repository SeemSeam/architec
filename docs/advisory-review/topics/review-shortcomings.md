# 当前审查能力短板

建议型工具在长期使用中能否被信任，主要取决于证据质量。当前最需要补足的是让建议可信、可行动、可累积。

## 主要短板

- 证据粒度偏粗，很多结论停留在文件、包或组件级，难以直接交给 coding agent 处理。
- 静态结构视角较强，但行为视角不足，还没有把改动频率、使用面和测试保护纳入判断。
- 时间视角不足，还不能识别连续下降、反复变差和恢复滞后。
- AI/vibe coding 特有坏味覆盖不足，尤其是近重复、影子实现和孤儿抽象。
- 跨边界耦合主要看 import，还没有覆盖共享类型、隐式契约、共享状态和稳定性倒置。
- 审查结果需要更强排序，避免把所有 concern 平铺成噪音清单。
- 项目特定 architecture contracts 已有第一步表达入口，可检查 changed-file-scoped restricted imports；ownership、facade/public API expectations 仍未覆盖。
- `plan-review` 和 `code-review --diff` 已有路径级连接，可识别 changed files 是否偏离 saved plan touchpoints；更深的 import-edge expectation 和语义意图匹配仍未覆盖。
- 外部 coverage/churn/test-map 已可作为 optional risk context 附加到结构 concern；complexity、public API 和更深历史风险融合仍未覆盖。

## 深化主线

- 可信：符号级证据、置信度分档、明确 evidence 来源。
- 可行动：blast radius、top concerns、结构叙事。
- 可累积：review 事件流、趋势分析、项目历史记忆。

这三条是深化审查能力的主线。新增信号必须服务于这三条，不能只为了扩大检查项数量。

下一阶段优先级见 [architecture-stability.md](architecture-stability.md)：architecture contracts、路径级 plan/diff consistency 和 risk context fusion 已有 v1；下一步应继续深化 contracts、plan/diff import-edge expectations，以及 complexity/public API 风险融合。
