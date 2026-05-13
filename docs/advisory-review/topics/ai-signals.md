# AI 特有审查信号

建议型工具的核心竞争力不是信号数量，而是证据质量。AI/vibe coding 场景的差异化价值来自识别普通 linter 和静态分析不容易覆盖的腐烂模式。

当前审查能力短板见 [review-shortcomings.md](review-shortcomings.md)。历史、测试、依赖和运行时信号见 [external-signals.md](external-signals.md)。

## 第一批信号

- `near_duplicate`：AST 或 token 指纹命中的近重复函数、类或文件。
- `shadow_implementation`：新增代码与已有能力高度相似，但没有复用既有入口。

`near_duplicate` v1 的范围见 [decisions/012-near-duplicate-v1-scope.md](../decisions/012-near-duplicate-v1-scope.md)：当前只在全量审查中检测 Python 函数/方法的规范化 AST 重复，优先低误报。

`shadow_implementation` v1 的函数级范围见 [decisions/022-shadow-implementation-v1-scope.md](../decisions/022-shadow-implementation-v1-scope.md)。class-level v1 见 [decisions/023-shadow-implementation-class-v1.md](../decisions/023-shadow-implementation-class-v1.md)。当前只在全量审查中检测 Python 函数和类级跨文件相似实现，优先高精度。

`shadow_implementation` v1 不是：

- `near_duplicate` 的替代。完全相同的规范化 AST 仍由 `near_duplicate` 报告。
- 合法 adapter、wrapper、facade 或兼容入口。
- 测试 fixture、生成代码、vendor 代码或 build artifact 检查。
- 增量审查信号；`--diff` / `--since` 暂不启用。
- 文件级模糊相似检查；当前只覆盖函数和类。

误报控制：

- 只扫描 Python 源文件，跳过 tests、fixtures、generated、vendor、build、dist、虚拟环境和本地生成目录。
- 只报告跨文件函数，不报告同文件 nested helper。
- 函数节点数至少 45。
- 类节点数至少 90，且需要 API/member shape 相似。
- 需要共享角色 token、名称 token overlap、签名相似度、AST feature cosine 和无直接复用边共同满足阈值。
- 输出 top candidates，并在 concern 中保留 `existing_implementation` 结构化 reference。

优先原因：

- 这两类是 vibe coding 最常见的“新写而不复用”腐烂形态。
- 证据相对可解释，可指向具体函数、类或文件。
- 适合先在全量审查中建立高置信观察，再评估增量范围控制。

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
