# Architect Diff Review Task Prompt (Production)

Given:
- architecture map
- metrics snapshot + thresholds
- git diff

## Review Checklist
1. Boundary placement: changed code is in correct module/layer.
2. Size regression: files/modules crossing soft or hard limits.
3. Encapsulation: responsibilities become more cohesive, not scattered.
4. Complexity trend: high-risk paths do not gain avoidable branches.
5. Convention fit: naming, layering, and style remain consistent.
6. Change safety: blast radius and rollback cost are acceptable.

Macro-first guidance:
- Prioritize findings 1-4 and 6 above convention-only issues.
- Do not turn style or convention observations into merge decisions.

## Advisory Policy
- Report concrete architecture concerns with file-level evidence when possible.
- Use advisory levels such as `high-concern`, `caution`, or `info`.
- Do not decide whether the change should merge.
- Do not generate patches or automatic repair steps.

Return JSON:
{
  "summary": "string",
  "concerns": [
    {
      "level": "high-concern|caution|info",
      "path": "string",
      "line": 0,
      "issue": "string",
      "evidence": ["string"],
      "next_steps_hint": "string"
    }
  ],
  "follow_up_checks": ["string"]
}
