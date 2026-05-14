# Architecture Stability Plan

`architec` can reduce architecture drift, but it cannot guarantee long-term code quality by itself. The product boundary remains advisory: it reports evidence, trends, and repair directions; humans and coding agents still decide and execute changes.

## Current Coverage

Current advisory-review coverage is strong for early structural warning:

- `code-review --diff` and `--since` keep incremental observations scoped to changed files.
- `code-review --full` reports cleanup/archive, hotspot, topology, duplication, and shadow-implementation signals.
- `near_duplicate` catches Python function-level normalized AST repeats in full and changed-file-scoped incremental reviews.
- `shadow_implementation` catches Python function/class implementations that look similar to existing implementations without reuse.
- `fix-advice --review <review.json>` gives advisory options for duplication and shadow-implementation concerns.
- `status --trend` reads review events so repeated weakening can be observed over time.
- Full generated concerns are written to `.architec/code-review-concerns.json`, while top-level JSON remains bounded.

This is enough to catch many vibe-coding drift patterns: repeated functions, reimplemented classes, hotspots gaining more responsibility, cleanup/archive debt, and package-boundary observations.

## Current Limits

The current system does not guarantee mainline quality:

- It does not prove behavior correctness or replace tests.
- It does not enforce merge decisions or block CI.
- It does not yet encode project-specific architecture contracts such as allowed dependency directions or ownership boundaries.
- It does not strongly compare a plan against the actual diff beyond the current plan-review and fingerprint foundation.
- It does not yet combine test coverage, churn, complexity, and review concerns into compound risk.
- File/module-level shadow implementation remains dry-run only because current evidence is not precise enough for a public signal.
- TypeScript/Go and other languages are still outside the current AI-signal scope.

## Next Capability Order

The next architecture-stability work should prioritize contract and drift controls over adding more smells.

1. **Architecture Contracts**

   Define project-owned boundary rules that code-review can evaluate:

   - package or directory ownership;
   - allowed import directions;
   - facade or public API requirements;
   - forbidden direct dependencies between layers;
   - generated/vendor/test/source scope boundaries.

   Output should remain advisory concerns, not pass/fail gates.

2. **Plan/Diff Consistency**

   Strengthen the link between `plan-review` and `code-review --diff`:

   - compare planned file/module touchpoints with actual changed files;
   - report unexpected dependency edges introduced by the diff;
   - highlight public API or boundary changes not described by the plan;
   - keep observations factual and scoped to the selected diff.

3. **Test/Churn Risk Fusion**

   Read existing project signals instead of executing a new test framework:

   - changed files without adjacent tests;
   - high churn plus hotspot or shadow/duplication concern;
   - public API changes without test coverage evidence;
   - repeated weakening in status events.

   These should become risk multipliers or companion signals, not verdicts.

4. **Module-Level Shadow Re-evaluation**

   Only revisit public file/module-level shadow implementation after:

   - real positive fixtures exist;
   - provider/plugin variant taxonomy is explicit;
   - source-root scoping is proven across multiple repositories;
   - dry-run candidates show low false-positive rates.

5. **Multi-Language Expansion**

   Add TypeScript/Go only after the Python signal model is stable. Start with import graph, symbol inventory, and duplicate/shadow primitives rather than full semantic analysis.

## Operating Model

Recommended use for long-term maintenance:

- run `archi code-review --diff . --out review.json` after coding-agent changes;
- run `archi fix-advice --review review.json` for the concerns worth acting on;
- run `archi code-review --full .` on a schedule or before larger releases;
- run `archi status --trend` to watch whether structural concerns are accumulating;
- keep boundary-contract decisions in versioned config or plan docs before asking agents to implement broad changes.

The intended effect is not a guarantee that the code is correct. It is a feedback loop that makes structural drift visible early enough that maintainers and agents can correct course.
