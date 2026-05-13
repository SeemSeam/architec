# fix-advice 修复建议

`fix-advice` 基于一次已存在 review 结果输出可考虑的修复方向。它不生成 patch，不执行修改，不做工作流编排。

## 输入

```bash
archi fix-advice --for <review.json>
```

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

如果旧 review 只有 `near_duplicate.reference=...` 这类 evidence string，`fix-advice` 可以作为兼容路径解析它。没有结构化 reference 且 evidence 不足时，输出 generic duplication advice，并说明 evidence insufficient。

该分支不判断哪个实现正确，不输出 patch，不承诺合并方向。

## 空/降级输出

- 如果 review 结果没有 concern，输出空 `suggestions` 和摘要说明。
- 如果某个 concern 没有足够证据生成修复建议，保留该 concern 的引用，并说明 `insufficient_evidence_for_fix_advice`。
- 如果 `--for <review.json>` 指向不存在的文件、无效 JSON，或顶层不是 object，CLI 返回错误，不静默生成空建议。
