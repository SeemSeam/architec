# 当前审查能力短板

建议型工具在长期使用中能否被信任，主要取决于证据质量。当前最需要补足的是让建议可信、可行动、可累积。

## 主要短板

- 证据粒度偏粗，很多结论停留在文件、包或组件级，难以直接交给 coding agent 处理。
- 静态结构视角较强，但行为视角不足，还没有把改动频率、使用面和测试保护纳入判断。
- 时间视角不足，还不能识别连续下降、反复变差和恢复滞后。
- AI/vibe coding 特有坏味覆盖不足，尤其是近重复、影子实现和孤儿抽象。
- 跨边界耦合主要看 import，还没有覆盖共享类型、隐式契约、共享状态和稳定性倒置。
- 审查结果需要更强排序，避免把所有 concern 平铺成噪音清单。
- 项目特定 architecture contracts 还没有表达入口，无法稳定检查 ownership、allowed dependency direction 或 facade/public API expectations。
- `plan-review` 和 `code-review --diff` 的连接还不够强，暂不能系统识别实现是否偏离了已审查的方案范围。
- 测试、coverage、churn 和 complexity 还没有与结构 concern 融合，暂不能识别“高 churn + 低测试 + 架构风险”的组合模式。

## 深化主线

- 可信：符号级证据、置信度分档、明确 evidence 来源。
- 可行动：blast radius、top concerns、结构叙事。
- 可累积：review 事件流、趋势分析、项目历史记忆。

这三条是深化审查能力的主线。新增信号必须服务于这三条，不能只为了扩大检查项数量。

下一阶段优先级见 [architecture-stability.md](architecture-stability.md)：先补 architecture contracts、plan/diff consistency 和 test/churn risk fusion，再评估更多 smell detectors。
