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
- Do not block solely for style/convention when boundary/safety are sound.

## Decision Policy
- `approve`: no critical finding and only minor warnings.
- `needs_changes`: at least one warning with clear remediation.
- `block`: critical boundary/safety/regression issue.

Return JSON:
{
  "summary": "string",
  "decision": "approve|needs_changes|block",
  "findings": [
    {
      "severity": "critical|warning|info",
      "path": "string",
      "line": 0,
      "issue": "string",
      "recommendation": "string"
    }
  ],
  "follow_up_tests": ["string"]
}
