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

## 空/降级输出

- 如果 review 结果没有 concern，输出空 `suggestions` 和摘要说明。
- 如果某个 concern 没有足够证据生成修复建议，保留该 concern 的引用，并说明 `insufficient_evidence_for_fix_advice`。
