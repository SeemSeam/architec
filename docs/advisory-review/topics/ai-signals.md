# AI 特有审查信号

建议型工具的核心竞争力不是信号数量，而是证据质量。AI/vibe coding 场景的差异化价值来自识别普通 linter 和静态分析不容易覆盖的腐烂模式。

当前审查能力短板见 [review-shortcomings.md](review-shortcomings.md)。历史、测试、依赖和运行时信号见 [external-signals.md](external-signals.md)。

## 第一批信号

- `near_duplicate`：AST 或 token 指纹命中的近重复函数、类或文件。
- `shadow_implementation`：新增代码与已有能力高度相似，但没有复用既有入口。

`near_duplicate` v1 的范围见 [decisions/012-near-duplicate-v1-scope.md](../decisions/012-near-duplicate-v1-scope.md)：当前只在全量审查中检测 Python 函数/方法的规范化 AST 重复，优先低误报。

优先原因：

- 这两类是 vibe coding 最常见的“新写而不复用”腐烂形态。
- 证据相对可解释，可指向具体函数、类或文件。
- 适合增量审查，只报告本次新增或恶化的重复/影子实现。

## 第二批信号

- `orphan_abstraction`：无调用者的类、接口、工厂或 helper，尤其是近期新增对象。
- `speculative_generality`：抽象参数化程度高，但实际只有单一用法。

第二批等第一批误报率可控后再做，不进入 4-6 周必交付。

## 优先级

第一梯队：

- 符号级证据下沉。
- `near_duplicate` 和 `shadow_implementation`。
- review 事件流和单维度趋势。
- concern 排序和相对健康坐标。
- plan 缺漏检查清单。

第二梯队：

- blast radius 和 API 变更检测。
- `churn × complexity` 动态风险。
- 深层耦合：shared type、implicit contract、stability inversion。
- 方案一致性观察细化到符号级。
- 测试信号轻度引入。

暂缓或不做：

- 自建运行时信号采集。
- 高误报风格漂移检查。
- 黑盒 ML 坏味发现。
- 自建 CVE/license/供应链扫描。
- 多语言扩展。
- 用户自定义脚本化规则平台。
