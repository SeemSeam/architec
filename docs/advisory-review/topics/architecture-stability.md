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

## Capability Matrix

| Maintenance goal | Current capability | Maturity |
| --- | --- | --- |
| Prevent obvious duplicate code | `near_duplicate` reports exact normalized Python function repeats in full and changed-file-scoped diff/since reviews. | Strong for exact Python function repeats; weak for fuzzy or cross-language repeats. |
| Detect repeated wheel-building | `shadow_implementation` reports Python function/class implementations that resemble an existing implementation without a reuse edge. | Strong for high-confidence symbol-level Python cases; module-level remains dry-run only. |
| Keep incremental reviews focused | `code-review --diff` and `--since` only report changed-file primary `near_duplicate` and `shadow_implementation` concerns. | Strong for avoiding historical-debt noise in incremental feedback. |
| Track architecture drift over time | review events plus `status --trend` can show recurring weakening components and score source history; optional risk context can attach coverage/churn/test-map facts to concerns. | Useful, but still depends on external report quality. |
| Preserve boundary intent | `.architecture-rules.toml` can encode changed-file-scoped restricted imports; topology and hotspot concerns expose structural pressure. | Partial. Ownership, facade expectations, and richer contracts remain future work. |
| Align implementation with a reviewed plan | Saved `plan-review` JSON can be supplied to `code-review --diff/--since` for path-level plan/diff consistency observations. | Partial. Stronger import-edge and semantic intent matching remain future work. |
| Protect mainline behavior | `architec` does not execute tests, prove behavior, or inspect runtime errors. | Out of scope unless external test/churn reports are supplied. |

## Guarantee Model

`architec` should be treated as an architecture feedback loop, not a proof system. It can make drift visible and harder to miss, but it cannot guarantee that the main branch is correct or maintainable without project process around it.

The practical guarantee target is narrower:

- every reviewed diff gets a bounded set of architecture concerns;
- repeated implementation and changed-file duplication are visible before they accumulate;
- project-specific boundary contracts can be checked once they are defined;
- trends can show whether structural pressure is increasing across reviews;
- fix-advice can turn concerns into neutral repair options.

The tool still depends on maintainers or coding agents to act on those observations. Long-term stability requires running it consistently and versioning the project rules it should enforce.

## Current Limits

The current system does not guarantee mainline quality:

- It does not prove behavior correctness or replace tests.
- It does not enforce merge decisions or block CI.
- It encodes first-step project-specific architecture contracts for changed-file import restrictions, but broader ownership and facade expectations remain future work.
- It only compares saved plan-review paths against selected changed files; deeper semantic intent and import-edge expectations remain future work.
- It only combines coverage, churn, and source-to-test facts when an external risk context JSON is supplied; it does not execute tests or collect those reports itself.
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

   First implementation target:

   - a small project-local config format for ownership and dependency direction;
   - import-edge extraction reused from existing topology analysis where possible;
   - new `architecture-contract` concerns with evidence such as source path, imported module, matched rule id, restricted import, and optional owner;
   - no default output when no contract config exists.

   V1 is recorded in [Decision 036](../decisions/036-architecture-contracts-v1.md). `fix-advice` options for contract concerns remain a later small step.

2. **Plan/Diff Consistency**

   Strengthen the link between `plan-review` and `code-review --diff`:

   - compare planned file/module touchpoints with actual changed files;
   - report unexpected dependency edges introduced by the diff;
   - highlight public API or boundary changes not described by the plan;
   - keep observations factual and scoped to the selected diff.

   First implementation target:

   - make `plan-review --out plan.json` or an equivalent saved plan artifact the explicit input;
   - compare planned touchpoints to `change_analysis.changed_files`;
   - surface `plan-diff-consistency` concerns for unexpected changed areas, missing expected areas, and boundary changes not named in the plan;
   - keep plan/diff mismatch as an observation, not a claim that the implementation is wrong.

   V1 is recorded in [Decision 037](../decisions/037-plan-diff-consistency-v1.md). It compares saved `plan-review` paths with changed files. Structured import-edge expectations are recorded in [Decision 040](../decisions/040-plan-diff-import-edge-expectations.md). Explicit expected-test entries are recorded in [Decision 045](../decisions/045-plan-diff-expected-tests.md); prose test notes remain context. Dependency alternatives are recorded in [Decision 046](../decisions/046-plan-diff-dependency-alternatives.md); any listed acceptable module can satisfy the planned dependency group. Public API migration touchpoints are recorded in [Decision 047](../decisions/047-plan-diff-public-api-migrations.md); prose migration notes remain context.

3. **Test/Churn Risk Fusion**

   Read existing project signals instead of executing a new test framework:

   - changed files without adjacent tests;
   - high churn plus hotspot or shadow/duplication concern;
   - public API changes without test coverage evidence;
   - repeated weakening in status events.

   These should become risk multipliers or companion signals, not verdicts.

   First implementation target:

   - read optional external reports from stable file paths or explicit CLI flags;
   - support simple JSON inputs for coverage-by-file, churn-by-file, and changed test files;
   - enrich existing concerns with companion risk facts rather than inventing a separate health score;
   - never execute the test runner as part of `code-review`.

   V1 is recorded in [Decision 039](../decisions/039-risk-context-fusion-v1.md). It reads an optional `--risk-context` JSON and adds companion evidence plus a `risk_context` signal. Complexity, public API, and historical recurrence enrichment are recorded in [Decision 044](../decisions/044-risk-context-enrichment.md); these facts still attach only to existing concerns.

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

## What Still Blocks Stronger Architecture Protection

The next major gap is not another generic smell detector. It is the absence of repository-specific rules. Without contracts, `architec` can say that code is getting more complex or duplicative, but it cannot know that `src/api` must not import `src/storage` directly, or that a feature package must only expose a facade.

The second gap is intent tracking. Vibe-coding drift often starts when implementation wanders away from a reviewed plan. Path-level plan/diff consistency is now available when a saved `plan-review` JSON is provided, but deeper semantic intent and import-edge expectations remain future work.

The third gap is risk fusion. Architecture concerns matter more when they appear in high-churn, under-tested, public API code. V1 can combine externally supplied coverage/churn/test-map facts with concerns, and Decision 044 extends that input model to optional complexity, public API, and historical recurrence facts. Richer external report formats and cross-event historical explanation remain future work.

These three gaps define the implementation sequence: contracts first, path-level plan/diff consistency second, test/churn fusion third.
