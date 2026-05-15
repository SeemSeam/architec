# fix-advice 修复建议

`fix-advice` 基于一次已存在 review 结果输出可考虑的修复方向。它不生成 patch，不执行修改，不做工作流编排。

## 输入

```bash
archi fix-advice --review <review.json>
```

`--for <review.json>` 保留为兼容别名；新示例使用 `--review`。

可选聚焦范围：

- 文件
- 组件
- 信号类别
- concern id

`concern_id` 用于引用一次 review 中的具体 concern。当前 code-review 生成的 id 基于 concern facts，而不是展示顺序；旧 review 中的位置型 id 仍可被读取。

## 输出

```json
{
  "mode": "fix_advice",
  "source_review": "",
  "suggestions": [
    {
      "target": "",
      "concern": "",
      "options": [],
      "tradeoffs": [],
      "risks": []
    }
  ],
  "artifacts": {}
}
```

## 语义边界

- 只输出修复建议，不生成 patch。
- 不提供 `--apply`。
- 每条建议可以独立采纳。
- 同一个问题可以给多个修复方向，由人或 coding agent 决定采用哪一个。
- 不承诺执行顺序。

`fix-advice` 面向一次已存在 review 的具体 concern；`plan-review` 的 `suggested_adjustments` 面向方案落地前的范围、位置和复用方向。两者不能混用。

## Duplication Advice

当 concern 的 `kind` 是 `duplication` 时，`fix-advice` 使用 duplication 专用建议分支。

如果 concern 提供 `references[]`，其中 `role: "reference"` 的条目会作为 reference implementation。duplicate implementation 仍来自 concern 的 `location`。建议输出会围绕这些 advisory options：

- 比较 duplicate 与 reference 的行为是否确实应共享。
- 如果行为应共享，可考虑让 duplicate 复用或路由到 reference implementation。
- 如果行为应分化，可在 duplicate 附近或调用者契约中说明差异。

如果 duplicate、reference 或 evidence 中有明确 legacy / compat / shim /
migration / deprecation intent，`fix-advice` 会额外给出 compatibility intent
选项：记录兼容路径意图，并把兼容 wrapper 或路径与 canonical
implementation 的关系说清楚。该选项不判断兼容路径应合并还是保留。

该 compatibility intent 仍只使用 duplication 的 reference 语义。
`references[].role: "existing_implementation"` 属于 shadow-implementation
建议分支，不作为 duplication reference 或 compatibility 证据消费。

如果旧 review 只有 `near_duplicate.reference=...` 这类 evidence string，`fix-advice` 可以作为兼容路径解析它。没有结构化 reference 且 evidence 不足时，输出 generic duplication advice，并说明 evidence insufficient。

该分支不判断哪个实现正确，不输出 patch，不承诺合并方向。

## Shadow Implementation Advice

当 concern 的 `kind` 是 `shadow-implementation` 时，`fix-advice` 使用 shadow implementation 专用建议分支。

该分支优先读取 `references[]` 中 `role: "existing_implementation"` 的结构化位置。疑似 shadow implementation 仍来自 concern 的 `location`。

函数级 concern 的建议围绕这些 advisory options：

- 比较 changed function 与 existing implementation 的行为是否确实应共享。
- 如果行为应共享，可考虑让 changed function 路由到或复用 existing implementation。
- 如果两者需要分离，可在 changed function 的局部契约或调用者说明中记录差异。

类级 concern 的建议围绕这些 advisory options：

- 比较 changed class 与 existing class 的职责、生命周期和配置上下文。
- 如果职责应共享，可考虑复用 existing class 或抽取稳定的共享行为。
- 如果上下文不同，可记录 intentional divergence，避免后续把两者误判为可合并。

如果 concern 缺少结构化 `existing_implementation` reference，输出保守 fallback，并说明 reference evidence insufficient。该分支不判断哪个实现正确，不输出 patch，不承诺合并方向。

## Architecture Contract Advice

当 concern 的 `kind` 是 `architecture-contract` 时，`fix-advice` 使用 contract 专用建议分支。

该分支读取 `architecture_contract.rule_id`、`architecture_contract.import`、`architecture_contract.restricted_import` 和可选 `architecture_contract.owner`。规则的 `note` 不进入 evidence，但会通过 concern 的 `next_steps_hint` 作为 review context 出现在建议里。

建议围绕这些 advisory options：

- 比较 changed file 中的 import 与匹配到的 contract。
- 如果 contract 应保持，可考虑通过已有边界、facade 或适配层路由依赖。
- 如果 direct dependency 是有意的，可更新 contract 记录或相关 plan，说明例外理由。

该分支不判断 contract 或 changed import 哪一方正确，不输出 patch，不承诺执行顺序。

## 空/降级输出

- 如果 review 结果没有 concern，或当前 filters 没有匹配 concern，输出空 `suggestions` 和中性摘要：`No fix advice suggestions were generated for this review.`
- 空 `suggestions` 会在 `summary.reason` 中说明 review has no matching concerns for the selected filters，不暗示 review 没有问题。
- 如果某个 concern 没有足够证据生成修复建议，保留该 concern 的引用，并说明 `insufficient_evidence_for_fix_advice`。
- 如果 `--review <review.json>` 或兼容别名 `--for <review.json>` 指向不存在的文件、无效 JSON，或顶层不是 object，CLI 返回错误，不静默生成空建议。
