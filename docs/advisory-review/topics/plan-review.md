# plan-review 方案审查

`plan-review` 审查已有方案 Markdown。它不生成方案，不评价方案是否应该做，只指出方案会撞上哪些项目事实、边界和历史模式。

## 输入

```bash
archi plan-review <plan.md>
archi plan-review <plan.md> --out plan.json
```

可选参数：

- 项目根路径，默认当前目录。
- 规则配置路径，默认使用项目默认规则。

当前版本只支持单个 plan 文件，不支持目录级多方案协同审查。

## 推荐模板

方案 Markdown 不要求写成长设计文档，但建议包含三段：

````md
# Plan

## Intent
Add near-duplicate signal review for AI-generated code.

## Changes
```yaml
changes:
  - action: create
    path: src/architec/analysis/signals.py
    intent: detect near-duplicate functions
  - action: modify
    path: src/architec/reporting/report_markdown.py
    intent: include signal summary in review output
dependencies: []
```

## Notes
Do not change cleanup archive behavior.
````

解析规则：

- fenced YAML 优先。
- fenced YAML 建议从行首开始，避免缩进、引用块或列表嵌套导致提取降级。
- Markdown 标题和正文作为上下文。
- 解析失败时降级，不输出 fail 或 reject。
- 输出 `understood_plan`，让作者确认 `architec` 是否读懂方案。

## 输出

```json
{
  "mode": "plan_review",
  "understood_plan": {
    "intent": "",
    "changes": [],
    "dependencies": []
  },
  "concerns": [],
  "suggested_adjustments": [],
  "plan_fingerprint": "",
  "artifacts": {}
}
```

语义边界：

- `concerns` 统一表达可能撞上的架构边界、已有实现、稳定性约束和热点区域。
- `suggested_adjustments` 表达可考虑的替代方向。复用已有实现属于一种 adjustment，而不是独立输出类别。
- `plan_fingerprint` 供后续 `code-review --diff` 做一致性观察。
- 保存后的 JSON 可通过 `archi code-review --diff --plan-review plan.json .` 或 `archi code-review --since <ref> --plan-review plan.json .` 与 selected changed files 做路径级一致性观察。
- `plan_fingerprint` 保留 YAML 中 `changes` 和 `dependencies` 的原始顺序；同一触达对象列表重新排序会生成不同 fingerprint。这让 fingerprint 表示“这份具体方案文本的承诺”，而不是去重后的对象集合。

## 空/降级输出

- 如果方案 Markdown 无法完整解析，仍输出 `understood_plan` 中已识别的部分，并把未识别内容作为自由文本上下文。
- 如果无法识别任何触达对象，返回空 `concerns` 和一条 `missing-context` concern，提示建议补充 Changes 块。
- 不因格式不足输出 fail 或 reject。

## 审查深化

`plan-review` 不应只复述方案里写了什么，还要基于项目现状做前视审查。

增强方向：

- 相似实现检查：方案计划新增的模块、文件或能力是否与已有实现相似。
- 影响范围估计：计划触达对象可能影响哪些调用者、组件和稳定包。
- 维度影响估计：方案可能影响哪些结构维度，例如 hotspot hygiene、cleanup hygiene、coupling control。
- 缺漏检查：方案是否触及多个包却没有提测试，是否新增依赖却没有提替代评估，是否修改 public API 却没有提迁移。

边界：

- 不评价方案是否“好”或“应该做”。
- 不生成替代完整方案。
- 不输出量化预测，只输出可能影响的维度名单和理由。
- 只回答“这份方案会撞上项目里的什么事实或历史模式”。
