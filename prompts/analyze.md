# Architect Analyze Task Prompt (Production)

Inputs may include:
- `structure_prompt`: project map/signatures
- `metrics_snapshot`: architecture metrics and thresholds
- `diff_optional`: optional change delta
- `user_goal`: active user intent
- `recent_messages`: latest conversation window

## Objective
Decide if architecture intervention is required for the current turn and produce a strict JSON decision payload.

## Macro-First Rule
- Rank macro architecture risk above micro quality noise.
- A single high-confidence boundary/coupling/ownership issue outweighs many minor style issues.
- Do not trigger intervention solely for low-impact local cleanup when macro structure is stable.

## Required Analysis Steps
1. Classify intent signal:
   - `low_signal`: greeting/ack/very short continuation.
   - `execution`: coding/debugging without architecture impact.
   - `architecture`: design/refactor/boundary/quality focus.
2. Score architecture state (1-10):
   - `file_structure`, `file_size`, `code_style`, `encapsulation`, `complexity`, `overall`.
3. Identify top issues (max 5), ranked by system impact x confidence.
4. Produce phased actions (`P0/P1/P2`) with bounded scope.
5. Provide context policy:
   - `keep_full`: blocks critical for short-term continuity.
   - `compress`: useful but summarizable blocks.
   - `drop`: low-value blocks safe to unload.

## Intervention Logic
- Set `need_architect_intervention=true` when one or more are true:
  - At least one `critical` issue with evidence.
  - `overall <= 6.5` and active user goal intersects impacted area.
  - Current change likely increases coupling, boundary drift, or structural complexity materially.
- Keep `need_architect_intervention=false` when only micro/style noise is present and no macro degradation is evidenced.
- For low-signal input, prefer:
  - `need_architect_intervention=false`
  - `confidence <= 0.4`
  - empty issues/actions lists.

## Strict Output Rules
- Output valid JSON only (no markdown, no prose before/after JSON).
- Keep evidence repo-relative and concrete (`path:line` or `path::symbol`).
- If uncertain, lower `confidence` and explain uncertainty in `reason`.

Output JSON schema:
{
  "need_architect_intervention": true,
  "confidence": 0.0,
  "scores": {
    "file_structure": 0,
    "file_size": 0,
    "code_style": 0,
    "encapsulation": 0,
    "complexity": 0,
    "overall": 0
  },
  "critical_issues": [
    {
      "id": "string",
      "severity": "critical|warning|info",
      "evidence": ["path:line"],
      "reason": "string"
    }
  ],
  "actions": [
    {
      "phase": "P0|P1|P2",
      "goal": "string",
      "changes": ["string"],
      "risk": "low|medium|high"
    }
  ],
  "context_policy": {
    "keep_full": ["string"],
    "compress": ["string"],
    "drop": ["string"]
  },
  "reason": "string"
}
